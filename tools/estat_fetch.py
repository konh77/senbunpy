#!/usr/bin/env python3
"""
e-Stat API から人口推計(年齢各歳・男女別)を取得し、data/raw/ に保存する。

背景: data/raw/ には人口を「年齢各歳」で持つファイルが存在しなかった(a101.xls は
家計調査だった)。手動ダウンロードの代わりにAPIを使うことで、build_init.py がバグらせた
Excelパースの事故(列インデックスの誤り、シートブロックの上書き)を構造的に避けられる。

セットアップ:
  1. https://www.e-stat.go.jp/api/ で「アプリケーションID」を発行
     (登録URL欄は localhost 不可。GitHubプロフィールURL等を使う)
  2. 以下を作成(このリポジトリにもvaultにもコミットしないこと):
       mkdir -p ~/.config/senbunpy
       echo 'ESTAT_APP_ID=xxxxx' > ~/.config/senbunpy/estat.env
       chmod 600 ~/.config/senbunpy/estat.env

statsDataId: 対象ページ(人口推計 各年10月1日現在人口 統計表001 年齢(各歳)，男女別人口
及び人口性比)の「API」タブに表示される値を STATS_DATA_ID に設定してから実行する。
sid=0003448228 は dbview 表示用IDで、API用の statsDataId とは別体系なので注意。

使い方:
  python3 tools/estat_fetch.py                 # 取得してdata/raw/に保存
  python3 tools/estat_fetch.py --stats-data-id 0003xxxxxx
  python3 tools/estat_fetch.py --dry-run        # URLとレスポンスの要約のみ表示
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
ENV_FILE = Path.home() / ".config" / "senbunpy" / "estat.env"
API_BASE = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

# 人口推計 各年10月1日現在人口 令和2年国勢調査基準 統計表001
# 年齢(各歳)，男女別人口及び人口性比－総人口，日本人人口
# 確認済み: dbview の sid=0003448228 と statsDataId は同じ値だった(常にそうとは限らない)。
STATS_DATA_ID = "0003448228"


def load_app_id() -> str:
    app_id = os.environ.get("ESTAT_APP_ID")
    if not app_id and ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("ESTAT_APP_ID="):
                app_id = line.split("=", 1)[1].strip().strip("\"'")
                break
    if not app_id:
        sys.exit(
            f"appId が見つかりません。\n"
            f"ESTAT_APP_ID を環境変数で渡すか、{ENV_FILE} に書いてください。\n"
            f"発行方法はこのファイル冒頭のコメントを参照。"
        )
    return app_id


def fetch(app_id: str, stats_data_id: str) -> dict:
    params = {
        "appId": app_id,
        "statsDataId": stats_data_id,
        "lang": "J",
        "metaGetFlg": "Y",
        "cntGetFlg": "N",
    }
    url = f"{API_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "senbunpy/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        sys.exit(f"リクエスト失敗: {type(e).__name__}: {e}")

    result = body.get("GET_STATS_DATA", {}).get("RESULT", {})
    status = result.get("STATUS")
    if status not in (0, "0"):
        sys.exit(
            f"e-Stat APIエラー STATUS={status}: {result.get('ERROR_MSG')}\n"
            f"STATUS=100は認証失敗(appId誤り)、300は statsDataId が存在しない、"
            f"を意味する。statsDataId が正しいか dbview の「API」タブで再確認すること。"
        )
    return body


def summarize(body: dict) -> None:
    data = body["GET_STATS_DATA"]["STATISTICAL_DATA"]
    total = data.get("RESULT_INF", {}).get("TOTAL_NUMBER")
    table_name = data.get("TABLE_INF", {}).get("TITLE", {})
    print(f"表題: {table_name}")
    print(f"件数: {total}")

    values = data.get("DATA_INF", {}).get("VALUE", [])
    print(f"VALUE件数: {len(values)}")
    if values:
        print("先頭5件:")
        for v in values[:5]:
            print(f"  {v}")


def main() -> None:
    ap = argparse.ArgumentParser(description="e-Stat から人口推計(年齢各歳・男女別)を取得")
    ap.add_argument("--stats-data-id", default=STATS_DATA_ID)
    ap.add_argument("--dry-run", action="store_true", help="保存せず要約だけ表示")
    ap.add_argument(
        "--out", default="population_by_age_estat.json", help="保存ファイル名(data/raw/配下)"
    )
    args = ap.parse_args()

    app_id = load_app_id()
    body = fetch(app_id, args.stats_data_id)
    summarize(body)

    if args.dry_run:
        return

    RAW.mkdir(parents=True, exist_ok=True)
    out_path = RAW / args.out
    out_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n保存: {out_path.relative_to(ROOT)}")
    print("次: build_init.py にこのファイルをパースする関数を追加してください。")


if __name__ == "__main__":
    main()
