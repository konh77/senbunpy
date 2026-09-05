import numpy as np

from engine.init_pop import (UNEMPLOYMENT_RATE, WAGE_SIGMA, 平均賃金,
                             年齢帯の値, 労働力率, 在学率)
from engine.params import (就業, 女, 男, 非労働力, 退職,
                           学生, 失業, 万円あたりの円)
from engine.state import 増やす
from engine.tax import 相続税額

最高齢 = 110
就労開始年齢 = 15
SCHOOL_END_AGE = 23
引退年齢 = 65
独立年齢 = 22
独立確率 = 0.03
法定相続人数 = 2
出生性比 = 0.512

出生率 = [(15, 0.002), (20, 0.020), (25, 0.070), (30, 0.090),
              (35, 0.050), (40, 0.011), (45, 0.0004), (50, 0.0)]


def 生命表などを作る(初期データ) -> dict:
    death = np.zeros((2, 最高齢 + 1))
    for 性別, 鍵 in ((男, "male"), (女, "female")):
        survival = np.array(初期データ["lifeTable"][鍵]["survival"])
        for 年齢 in range(最高齢 + 1):
            if 年齢 + 1 >= len(survival) or survival[年齢] <= 0:
                death[性別, 年齢] = 1.0
                continue
            yearly = min(max(1.0 - survival[年齢 + 1] / survival[年齢], 0.0), 1.0)
            death[性別, 年齢] = 1.0 - (1.0 - yearly) ** (1.0 / 12.0)

    birth = np.zeros(最高齢 + 1)
    for 年齢 in range(最高齢 + 1):
        for start, 割合 in 出生率:
            if 年齢 >= start:
                birth[年齢] = 割合

    帯 = []
    for 見出し, wage in 初期データ["wageByAge"].items():
        if 見出し.startswith("~"):
            low, high = 0, int(見出し[1:])
        elif 見出し.endswith("~"):
            low, high = int(見出し[:-1]), 最高齢
        else:
            low, high = (int(x) for x in 見出し.split("~"))
        帯.append([low, high, wage])

    return {"death": death, "birth": birth, "wage_bands": 帯}


def 人口フェーズ(国, 台帳, 乱数, 設定, 早見表) -> None:
    if 国.経過月 % 12 == 11:
        年を取る(国, 乱数, 早見表)

    国.死亡数 = 死亡(国, 乱数, 早見表)
    国.出生数 = 出生(国, 乱数, 早見表)
    独立する(国, 乱数)
    世帯を数え直す(国)
    国.相続件数 = 相続する(国, 台帳, 設定)


def 年を取る(国, 乱数, 早見表) -> None:
    個人 = 国.個人
    個人.年齢[個人.生存 & (個人.年齢 < 最高齢)] += 1

    joining = 個人.生存 & ((個人.年齢 == 就労開始年齢) | (個人.年齢 == SCHOOL_END_AGE))
    仕事を割り当てる(国, np.flatnonzero(joining), 乱数, 早見表)

    retiring = 個人.生存 & (個人.年齢 == 引退年齢)
    個人.就業状態[retiring] = 退職
    個人.月給[retiring] = 0.0
    個人.労働時間[retiring] = 0.0
    個人.勤務先[retiring] = -1


def 仕事を割り当てる(国, 人々, 乱数, 早見表) -> None:
    個人 = 国.個人
    for i in 人々:
        年齢, 性別 = int(個人.年齢[i]), int(個人.性別[i])
        wage = 0.0

        if 乱数.random() < 在学率(年齢):
            個人.就業状態[i] = 学生
        elif 乱数.random() < 労働力率(年齢, 性別):
            if 乱数.random() < 年齢帯の値(UNEMPLOYMENT_RATE, 年齢):
                個人.就業状態[i] = 失業
            else:
                個人.就業状態[i] = 就業
                ばらつき = 乱数.lognormal(-WAGE_SIGMA * WAGE_SIGMA / 2, WAGE_SIGMA)
                wage = 平均賃金(早見表["wage_bands"], 年齢) * ばらつき * 万円あたりの円
                個人.勤務先[i] = int(乱数.integers(国.企業.総数))
        else:
            個人.就業状態[i] = 非労働力

        個人.月給[i] = wage
        個人.労働時間[i] = 1.0 if wage > 0 else 0.0


def 死亡(国, 乱数, 早見表) -> int:
    個人 = 国.個人
    確率 = 早見表["death"][個人.性別, np.minimum(個人.年齢, 最高齢)]
    死亡者 = 個人.生存 & (乱数.random(個人.総数) < 確率)

    個人.生存[死亡者] = False
    個人.就業状態[死亡者] = 非労働力
    個人.月給[死亡者] = 0.0
    個人.労働時間[死亡者] = 0.0
    個人.勤務先[死亡者] = -1
    return int(死亡者.sum())


def 出生(国, 乱数, 早見表) -> int:
    個人 = 国.個人
    確率 = 早見表["birth"][np.minimum(個人.年齢, 最高齢)] / 12.0
    mothers = 個人.生存 & (個人.性別 == 女)
    出産する母 = mothers & (乱数.random(個人.総数) < 確率)
    count = int(出産する母.sum())
    if count == 0:
        return 0

    世帯 = 個人.世帯番号[出産する母]
    最初 = 増やす(個人, count)
    新しい番号 = np.arange(最初, 最初 + count)

    個人.性別[新しい番号] = np.where(乱数.random(count) < 出生性比, 男, 女)
    個人.世帯番号[新しい番号] = 世帯
    個人.出生世帯[新しい番号] = 世帯
    個人.就業状態[新しい番号] = 非労働力
    個人.勤務先[新しい番号] = -1
    個人.生存[新しい番号] = True
    return count


def 独立する(国, 乱数) -> int:
    個人, 世帯 = 国.個人, 国.世帯

    can_leave = (個人.生存 & (個人.年齢 >= 独立年齢)
                 & (個人.就業状態 == 就業)
                 & (世帯.世帯人員[個人.世帯番号] >= 2))
    独立する人 = can_leave & (乱数.random(個人.総数) < 独立確率)

    count = int(独立する人.sum())
    if count == 0:
        return 0

    最初 = 増やす(世帯, count)
    個人.世帯番号[独立する人] = np.arange(最初, 最初 + count)
    return count


def 世帯を数え直す(国) -> None:
    個人, 世帯 = 国.個人, 国.世帯
    生存 = 個人.生存.astype(float)

    世帯.世帯人員[:] = np.bincount(個人.世帯番号, weights=生存, minlength=世帯.総数)
    世帯.子ども数[:] = np.bincount(
        個人.世帯番号, weights=生存 * (個人.年齢 < 18), minlength=世帯.総数)

    世帯.世帯主年齢[:] = 0
    if 個人.生存.any():
        np.maximum.at(世帯.世帯主年齢, 個人.世帯番号[個人.生存], 個人.年齢[個人.生存])


def 存続世帯(世帯) -> np.ndarray:
    return 世帯.世帯人員 > 0


def 相続する(国, 台帳, 設定) -> int:
    世帯, 個人 = 国.世帯, 国.個人
    消えた世帯 = np.flatnonzero((世帯.世帯人員 == 0) & (世帯.貯蓄 > 0))
    if len(消えた世帯) == 0:
        return 0

    遺産 = 世帯.貯蓄[消えた世帯]
    税 = 相続税額(遺産, 法定相続人数, 設定.get("相続税上乗せ", 0.0), 設定)
    台帳.一括送金("家計", "政府", 税, "相続税")

    世帯.貯蓄[消えた世帯] = 0
    left = 遺産 - 税

    escheat = 0
    for index, 世帯番号 in enumerate(消えた世帯):
        子ども数 = 個人.生存 & (個人.出生世帯 == 世帯番号)
        相続人たち = np.unique(個人.世帯番号[子ども数])
        相続人たち = 相続人たち[世帯.世帯人員[相続人たち] > 0]

        if len(相続人たち) == 0:
            escheat += int(left[index])
            continue
        each = int(left[index]) // len(相続人たち)
        世帯.貯蓄[相続人たち] += each
        世帯.貯蓄[相続人たち[0]] += int(left[index]) - each * len(相続人たち)

    if escheat:
        台帳.送金("家計", "政府", escheat, "国庫帰属")

    return len(消えた世帯)
