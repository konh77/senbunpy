import numpy as np
from numpy.random import default_rng

from engine.consumption import 基礎バスケットを作る, 消費フェーズ
from engine.demography import 生命表などを作る, 人口フェーズ
from engine.effects import 施行済みを適用, 最初の施行月
from engine.government import 政府フェーズ
from engine.income import 所得フェーズ
from engine.init_pop import 人口を生成する, 初期データを読む
from engine.ledger import 会計台帳
from engine.metrics import 指標履歴
from engine.params import 品目一覧, 既定設定
from engine.state import 国家
from engine.town import 街の記録


def 一月進める(国: 国家, 台帳: 会計台帳, 乱数, 設定: dict, バスケット, 履歴=None,
         法律の命令列=None, 慣らし月数: int = 0, 早見表=None, 街=None) -> None:
    基礎量, 限界配分 = バスケット
    設定, 有効な法律 = 施行済みを適用(法律の命令列, 国, 設定, 慣らし月数)

    if 早見表 is not None:
        人口フェーズ(国, 台帳, 乱数, 設定, 早見表)

    所得フェーズ(国, 台帳, 設定, 有効な法律)
    消費フェーズ(国, 台帳, 設定, 基礎量, 限界配分, 有効な法律)
    政府フェーズ(国, 台帳, 設定)

    if 履歴 is not None:
        履歴.記録する(国.経過月, 国, 台帳, 設定)
    if 街 is not None:
        街.記録する(国, 台帳)

    台帳.保存則を検算()
    台帳.月を締める()
    国.経過月 += 1


def 走らせる(月数: int, 乱数の種: int, 法律の命令列=None) -> dict:
    乱数 = default_rng(乱数の種)

    初期データ = 初期データを読む()
    国 = 人口を生成する(初期データ, 乱数, 既定設定["人口"])

    stock_households = int(国.世帯.貯蓄.sum())
    stock_firms = int(国.企業.資本.sum())
    台帳 = 会計台帳(opening={
        "家計": stock_households,
        "企業": stock_firms,
        "政府": -(stock_households + stock_firms),
    })

    shares = np.array([初期データ["spendShare"][c] for c in 品目一覧])
    バスケット = 基礎バスケットを作る(shares, 既定設定)
    早見表 = 生命表などを作る(初期データ)

    慣らし月数 = min(既定設定["慣らし月数"], 月数)
    履歴 = 指標履歴(慣らし月数=慣らし月数)
    街 = 街の記録(国, 乱数)
    街.属性を固める(国)

    for _ in range(月数):
        一月進める(国, 台帳, 乱数, 既定設定, バスケット, 履歴=履歴,
             法律の命令列=法律の命令列, 慣らし月数=慣らし月数, 早見表=早見表, 街=街)

    結果 = 履歴.辞書にする()
    結果["施行月"] = 最初の施行月(法律の命令列, 慣らし月数)
    結果["街"] = 街.辞書にする()
    return 結果


if __name__ == "__main__":
    out = 走らせる(120, 乱数の種=42)
    last = len(out["月数"]) - 1
    def show(v):
        return f"{v/1e8:,.1f}億円" if abs(v) >= 1e8 else f"{v:,.4f}"

    print(f"{'指標':<22}{'0ヶ月目':>18}{'120ヶ月目':>18}")
    for 鍵 in ("人口", "GDP", "所得ジニ", "資産ジニ", "消費税の逆進性",
                "政府債務", "失業率"):
        最初, final = out["系列"][鍵][0], out["系列"][鍵][last]
        print(f"{鍵:<22}{show(最初):>18}{show(final):>18}")
