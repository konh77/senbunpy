from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dsl.errors import 法律エラー

ROOT = Path(__file__).resolve().parent.parent
LAWS_DIR = ROOT / "laws"
WEB_DIR = ROOT / "web"
ARCHIVE_DIR = ROOT / "archive-web"

月数の上限 = 240

同時実行数 = int(os.environ.get("SENBUN_MAX_CONCURRENT", "2"))
_slots = threading.BoundedSemaphore(同時実行数)

app = FastAPI(title="千分の一の国", version="0.1.0")

ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000",
           "http://localhost:5500", "http://127.0.0.1:5500"]
ORIGINS += [o.strip() for o in os.environ.get("SENBUN_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class 実行要求(BaseModel):
    月数: int = Field(default=60, ge=1, le=月数の上限)
    乱数の種: int = Field(default=42, ge=0, le=2**31 - 1)
    法律: str = Field(default="", max_length=20_000)


def 法律エラーを400に(err) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "種類": type(err).__name__,
            "本文": str(getattr(err, "本文", err)),
            "行": getattr(err, "行", None),
            "桁": getattr(err, "桁", None),
            "助言": getattr(err, "助言", None),
        },
    )


def 未実装を503に(対象: str) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "種類": "NotImplemented",
            "本文": f"{対象} がまだ実装されていません。",
            "助言": "engine と dsl の該当モジュールを確認してください。",
            "行": None,
            "桁": None,
        },
    )


def 法律を翻訳する(source: str) -> tuple[list, list]:
    from dsl.compiler import 法律を翻訳する as _compile
    from dsl.parser import 解析する
    from dsl.validator import 検証する

    構文木 = 解析する(source)
    警告の並び = 検証する(構文木) or []
    return _compile(構文木), 警告の並び


_法律なしの控え: dict = {}
_控えの上限 = 8


def 法律なしを走らせる(月数: int, 乱数の種: int) -> dict:
    """法律なしの結果は seed と月数が同じなら必ず同一なので使い回す。

    同じ世界を毎回作り直す必要がない。決定性テストがこの前提を保証している。
    """
    鍵 = (月数, 乱数の種)
    if 鍵 not in _法律なしの控え:
        if len(_法律なしの控え) >= _控えの上限:
            _法律なしの控え.pop(next(iter(_法律なしの控え)))
        _法律なしの控え[鍵] = 走らせて返す(月数, 乱数の種, None)
    return _法律なしの控え[鍵]


def 走らせて返す(月数: int, 乱数の種: int, 法律の命令列: list | None) -> dict:
    from engine.engine import 走らせる

    return 走らせる(月数=月数, 乱数の種=乱数の種, 法律の命令列=法律の命令列)


@app.get("/api/health")
def 生存確認() -> dict:
    return {"正常": True}


@app.get("/api/laws")
def 例文を返す() -> list[dict]:
    if not LAWS_DIR.is_dir():
        return []
    out = []
    for path in sorted(LAWS_DIR.glob("*.law")):
        out.append({"名前": path.stem, "本文": path.read_text(encoding="utf-8")})
    return out


@app.post("/api/run")
def 実行を受ける(req: 実行要求) -> dict:
    source = req.法律.strip()

    law_meta = None
    法律の命令列 = None
    警告の並び: list = []

    if source:
        try:
            法律の命令列, 警告の並び = 法律を翻訳する(source)
        except (NotImplementedError, ImportError, AttributeError):
            raise 未実装を503に("DSL(lexer/parser/validator/compiler)")
        except 法律エラー as err:
            raise 法律エラーを400に(err)
        law_meta = {"命令列": 法律の命令列}

    if not _slots.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail={"種類": "Busy", "本文": "いま混み合っています。少し待って試してください。",
                    "助言": None, "行": None, "桁": None},
            headers={"Retry-After": "5"},
        )
    try:
        baseline = 法律なしを走らせる(req.月数, req.乱数の種)
        treatment = 走らせて返す(req.月数, req.乱数の種, 法律の命令列) if 法律の命令列 else None
    except (NotImplementedError, ImportError, AttributeError):
        raise 未実装を503に("エンジン(engine.run)")
    finally:
        _slots.release()

    return {
        "月数": req.月数,
        "乱数の種": req.乱数の種,
        "施行月": (treatment or {}).get("施行月"),
        "法律": law_meta,
        "警告": [str(w) for w in 警告の並び],
        "実行結果": {"法律なし": baseline, "施行後": treatment},
    }


if ARCHIVE_DIR.is_dir():
    app.mount("/archive", StaticFiles(directory=ARCHIVE_DIR, html=True), name="archive")

if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")


@app.middleware("http")
async def 画面はキャッシュさせない(request, call_next):
    """HTML と例文だけ no-store。編集した内容が古い画面で隠れるのを防ぐ。"""
    応答 = await call_next(request)
    if not request.url.path.startswith("/api") or request.url.path == "/api/laws":
        応答.headers["Cache-Control"] = "no-store"
    return 応答


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)
