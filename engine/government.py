import numpy as np

歳入の名目 = ("所得税", "社会保険料", "消費税", "相続税", "国庫帰属")
歳出の名目 = ("年金", "公共サービス", "利子", "給付")


def 利子を支払う(国, 台帳, 設定: dict) -> np.ndarray:
    債務 = 政府債務(台帳)
    if 債務 <= 0:
        return np.zeros(国.世帯.総数, dtype=np.int64)

    合計 = int(round(債務 * 設定["国債利率"] / 12))
    貯蓄 = 国.世帯.貯蓄.astype(np.float64)
    原資 = 貯蓄.sum()
    if 合計 <= 0 or 原資 <= 0:
        return np.zeros(国.世帯.総数, dtype=np.int64)

    取り分 = np.maximum(np.rint(貯蓄 / 原資 * 合計).astype(np.int64), 0)

    端数 = 合計 - int(取り分.sum())
    if 端数 != 0:
        最も裕福な世帯 = int(np.argmax(貯蓄))
        取り分[最も裕福な世帯] = max(取り分[最も裕福な世帯] + 端数, 0)

    台帳.一括送金("政府", "家計", 取り分, "利子")
    return 取り分


def 歳入(台帳) -> int:
    return sum(台帳.名目別.get(名目, 0) for 名目 in 歳入の名目)


def 歳出(台帳) -> int:
    return sum(台帳.名目別.get(名目, 0) for 名目 in 歳出の名目)


def 政府フェーズ(国, 台帳, 設定: dict) -> None:
    サービス費 = int(round(歳入(台帳) * 設定["公共サービス比率"]))
    台帳.送金("政府", "企業", サービス費, "公共サービス")
    国.サービス水準 = 1.0


def 財政収支(台帳) -> int:
    return 台帳.今月の増減["政府"]


def 政府債務(台帳) -> int:
    return -(台帳.残高["政府"] + 台帳.今月の増減["政府"])
