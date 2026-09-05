import numpy as np

from engine.effects import 給付を配る
from engine.government import 利子を支払う
from engine.params import 就業, 退職
from engine.tax import 所得税年額, 課税所得


def 所得フェーズ(国, 台帳, 設定: dict, 有効な法律=None) -> None:
    個人 = 国.個人
    世帯 = 国.世帯

    就業者 = 個人.就業状態 == 就業
    額面 = np.rint(np.where(就業者, 個人.月給 * 個人.労働時間, 0.0)).astype(np.int64)
    社会保険料 = np.rint(額面 * 設定["社会保険料率"]).astype(np.int64)

    税 = 所得税年額(課税所得(額面 * 12), 設定.get("所得税上乗せ", 0.0)) // 12
    手取り = 額面 - 社会保険料 - 税

    年金 = np.where(個人.就業状態 == 退職, 設定["年金月額"], 0).astype(np.int64)
    利子 = 利子を支払う(国, 台帳, 設定)

    台帳.一括送金("企業", "家計", 額面, "賃金")
    台帳.一括送金("家計", "政府", 社会保険料, "社会保険料")
    台帳.一括送金("家計", "政府", 税, "所得税")
    台帳.一括送金("政府", "家計", 年金, "年金")

    世帯.所得[:] = np.rint(
        np.bincount(個人.世帯番号, weights=手取り + 年金, minlength=世帯.総数)
    ).astype(np.int64) + 利子
    世帯.貯蓄 += 世帯.所得

    if 有効な法律:
        給付を配る(有効な法律, 国, 台帳, 設定)

    企業 = 国.企業
    賃金支払 = np.bincount(個人.勤務先[就業者], weights=額面[就業者], minlength=企業.総数)
    企業.資本 -= 賃金支払[: 企業.総数]
