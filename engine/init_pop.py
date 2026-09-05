import json
from pathlib import Path

import numpy as np
from numpy.random import default_rng

from engine.params import (品目一覧, 既定設定, 年齢別資産,
                           資産のばらつき, 万円あたりの円)
from engine.params import 男, 女
from engine.params import 非労働力, 就業, 失業, 学生, 退職
from engine.state import 国家, 国を用意する

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "json" / "data_init.json"

最高齢 = 110
SCHOOL_AGE = 15
成人年齢 = 18
RETIREMENT_AGE = 65
ELDERLY_AGE = 65

STUDENT_RATE = {
    15: 0.98, 16: 0.98, 17: 0.97, 18: 0.62,
    19: 0.60, 20: 0.57, 21: 0.55, 22: 0.28,
}

PARTICIPATION_MALE = {
    15: 0.35, 20: 0.72, 25: 0.94, 30: 0.96, 35: 0.96,
    40: 0.96, 45: 0.96, 50: 0.95, 55: 0.93, 60: 0.84,
}

PARTICIPATION_FEMALE = {
    15: 0.35, 20: 0.75, 25: 0.87, 30: 0.80, 35: 0.78,
    40: 0.82, 45: 0.84, 50: 0.82, 55: 0.76, 60: 0.63,
}

UNEMPLOYMENT_RATE = {
    15: 0.045, 20: 0.040, 25: 0.030, 30: 0.024, 35: 0.022,
    40: 0.021, 45: 0.021, 50: 0.021, 55: 0.023, 60: 0.026,
}

WAGE_SIGMA = 0.35
FULL_TIME_HOURS = 1.0

COUPLE_MIN_AGE = 22
PARENT_MIN_AGE = 25
PARENT_MIN_GAP = 18
COUPLE_AGE_SPREAD = 5
OFFSPRING_MAX_AGE = 49
LONE_MOTHER_CHANCE = 0.85
COUPLE_CHILD_CHANCES = [0.45, 0.42, 0.13]
LONE_CHILD_CHANCES = [0.68, 0.27, 0.05]

FIRM_CAPITAL_MONTHS = 3.0

NOBODY = -1


def 初期データを読む(path=DATA_FILE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def 確率で選ぶ(確率の並び, 乱数):
    roll = 乱数.random()
    合計 = 0.0
    for index in range(len(確率の並び)):
        合計 = 合計 + 確率の並び[index]
        if roll < 合計:
            return index
    return len(確率の並び) - 1


def 空の名簿():
    原資 = []
    for 年齢 in range(最高齢 + 1):
        原資.append([])
    return 原資


def 名簿の人数(原資):
    return sum(map(len, 原資))


def 名簿から取る(原資, 下限年齢, 上限年齢, 乱数):
    if 下限年齢 < 0:
        下限年齢 = 0
    if 上限年齢 > 最高齢:
        上限年齢 = 最高齢

    合計 = sum(map(len, 原資[下限年齢:上限年齢 + 1]))
    if 合計 == 0:
        return NOBODY

    wanted = int(乱数.integers(合計))
    for 年齢 in range(下限年齢, 上限年齢 + 1):
        if wanted < len(原資[年齢]):
            return 原資[年齢].pop()
        wanted = wanted - len(原資[年齢])
    return NOBODY


def 配偶者を取る(原資, wanted_age, 乱数):
    for 端数 in range(COUPLE_AGE_SPREAD + 1):
        for 年齢 in [wanted_age - 端数, wanted_age + 端数]:
            if 0 <= 年齢 <= 最高齢 and len(原資[年齢]) > 0:
                return 原資[年齢].pop()
    return NOBODY


def 大人を取る(男の名簿, 女の名簿, 下限年齢, 上限年齢, 乱数):
    if 乱数.random() < 0.5:
        first_pool = 男の名簿
        second_pool = 女の名簿
    else:
        first_pool = 女の名簿
        second_pool = 男の名簿

    人 = 名簿から取る(first_pool, 下限年齢, 上限年齢, 乱数)
    if 人 == NOBODY:
        人 = 名簿から取る(second_pool, 下限年齢, 上限年齢, 乱数)
    return 人


def 夫婦を取る(年齢の並び, 男の名簿, 女の名簿, 下限年齢, 乱数):
    夫 = 名簿から取る(男の名簿, 下限年齢, 最高齢, 乱数)
    if 夫 != NOBODY:
        妻 = 配偶者を取る(女の名簿, 年齢の並び[夫], 乱数)
        if 妻 == NOBODY:
            return [夫]
        return [夫, 妻]

    妻 = 名簿から取る(女の名簿, 下限年齢, 最高齢, 乱数)
    if 妻 == NOBODY:
        return []
    夫 = 配偶者を取る(男の名簿, 年齢の並び[妻], 乱数)
    if 夫 == NOBODY:
        return [妻]
    return [妻, 夫]


def 子を取る(子ども数, 男の名簿, 女の名簿, oldest_allowed, 乱数):
    子 = 名簿から取る(子ども数, 0, min(oldest_allowed, 成人年齢 - 1), 乱数)
    if 子 != NOBODY:
        return 子
    if oldest_allowed < 成人年齢:
        return NOBODY
    return 大人を取る(男の名簿, 女の名簿, 成人年齢, min(oldest_allowed, OFFSPRING_MAX_AGE), 乱数)


def 年齢と性別を作る(初期データ, 乱数, 総数):
    male_shares = 初期データ["population"]["male"]
    female_shares = 初期データ["population"]["female"]

    all_shares = male_shares + female_shares
    合計 = sum(all_shares)
    確率の並び = []
    for 取り分 in all_shares:
        確率の並び.append(取り分 / 合計)

    年齢の並び = []
    性別の並び = []
    for 人 in range(総数):
        picked = 確率で選ぶ(確率の並び, 乱数)
        if picked < len(male_shares):
            年齢の並び.append(picked)
            性別の並び.append(男)
        else:
            年齢の並び.append(picked - len(male_shares))
            性別の並び.append(女)
    return 年齢の並び, 性別の並び


def 在学率(年齢):
    if 年齢 in STUDENT_RATE:
        return STUDENT_RATE[年齢]
    return 0.0


def 年齢帯の値(table, 年齢):
    確率 = 0.0
    for start_age in sorted(table.keys()):
        if 年齢 >= start_age:
            確率 = table[start_age]
    return 確率


def 労働力率(年齢, 性別):
    if 性別 == 男:
        return 年齢帯の値(PARTICIPATION_MALE, 年齢)
    return 年齢帯の値(PARTICIPATION_FEMALE, 年齢)


def 就業状態を作る(年齢の並び, 性別の並び, 乱数):
    就業状態 = []
    for 人 in range(len(年齢の並び)):
        年齢 = 年齢の並び[人]
        if 年齢 < SCHOOL_AGE:
            就業状態.append(非労働力)
        elif 年齢 >= RETIREMENT_AGE:
            就業状態.append(退職)
        elif 乱数.random() < 在学率(年齢):
            就業状態.append(学生)
        elif 乱数.random() < 労働力率(年齢, 性別の並び[人]):
            if 乱数.random() < 年齢帯の値(UNEMPLOYMENT_RATE, 年齢):
                就業状態.append(失業)
            else:
                就業状態.append(就業)
        else:
            就業状態.append(非労働力)
    return 就業状態


def 賃金帯を読む(wage_by_age):
    帯 = []
    for 見出し in wage_by_age:
        wage = wage_by_age[見出し]
        if 見出し.startswith("~"):
            下限年齢 = 0
            上限年齢 = int(見出し[1:])
        elif 見出し.endswith("~"):
            下限年齢 = int(見出し[:-1])
            上限年齢 = 最高齢
        else:
            parts = 見出し.split("~")
            下限年齢 = int(parts[0])
            上限年齢 = int(parts[1])
        帯.append([下限年齢, 上限年齢, wage])
    return 帯


def 平均賃金(帯, 年齢):
    for 一帯 in 帯:
        下限年齢 = 一帯[0]
        上限年齢 = 一帯[1]
        wage = 一帯[2]
        if 下限年齢 <= 年齢 <= 上限年齢:
            return wage
    return 0.0


def 賃金を作る(帯, 年齢の並び, 就業状態, 乱数):
    賃金の並び = []
    for 人 in range(len(年齢の並び)):
        if 就業状態[人] == 就業:
            middle = -WAGE_SIGMA * WAGE_SIGMA / 2
            ばらつき = 乱数.lognormal(middle, WAGE_SIGMA)
            manyen = 平均賃金(帯, 年齢の並び[人]) * ばらつき
            賃金の並び.append(manyen * 万円あたりの円)
        else:
            賃金の並び.append(0.0)
    return 賃金の並び


def 子を加える(構成員, 年齢の並び, 子ども数, 男の名簿, 女の名簿, 確率の並び, 乱数):
    if len(構成員) == 0:
        return

    youngest_parent = 最高齢
    for 人 in 構成員:
        if 年齢の並び[人] < youngest_parent:
            youngest_parent = 年齢の並び[人]

    oldest_allowed = youngest_parent - PARENT_MIN_GAP
    how_many = 1 + 確率で選ぶ(確率の並び, 乱数)
    for step in range(how_many):
        子 = 子を取る(子ども数, 男の名簿, 女の名簿, oldest_allowed, 乱数)
        if 子 == NOBODY:
            return
        構成員.append(子)


def 世帯を組む(種類, 年齢の並び, 子ども数, 男の名簿, 女の名簿, 乱数):
    if 種類 == "単独":
        人 = 大人を取る(男の名簿, 女の名簿, 成人年齢, 最高齢, 乱数)
        if 人 == NOBODY:
            return []
        return [人]

    if 種類 == "夫婦のみ":
        return 夫婦を取る(年齢の並び, 男の名簿, 女の名簿, COUPLE_MIN_AGE, 乱数)

    if 種類 == "夫婦+子":
        構成員 = 夫婦を取る(年齢の並び, 男の名簿, 女の名簿, PARENT_MIN_AGE, 乱数)
        子を加える(構成員, 年齢の並び, 子ども数, 男の名簿, 女の名簿, COUPLE_CHILD_CHANCES, 乱数)
        return 構成員

    if 種類 == "ひとり親+子":
        if 乱数.random() < LONE_MOTHER_CHANCE:
            親世帯 = 名簿から取る(女の名簿, PARENT_MIN_AGE, 最高齢, 乱数)
        else:
            親世帯 = 名簿から取る(男の名簿, PARENT_MIN_AGE, 最高齢, 乱数)
        if 親世帯 == NOBODY:
            return []
        構成員 = [親世帯]
        子を加える(構成員, 年齢の並び, 子ども数, 男の名簿, 女の名簿, LONE_CHILD_CHANCES, 乱数)
        return 構成員

    構成員 = 夫婦を取る(年齢の並び, 男の名簿, 女の名簿, PARENT_MIN_AGE, 乱数)
    子を加える(構成員, 年齢の並び, 子ども数, 男の名簿, 女の名簿, LONE_CHILD_CHANCES, 乱数)
    if len(構成員) > 0:
        grandparent = 大人を取る(男の名簿, 女の名簿, ELDERLY_AGE, 最高齢, 乱数)
        if grandparent != NOBODY:
            構成員.append(grandparent)
    return 構成員


def 各世帯の最年長(世帯, 年齢の並び):
    oldest = []
    for 構成員 in 世帯:
        top_age = 0
        for 人 in 構成員:
            if 年齢の並び[人] > top_age:
                top_age = 年齢の並び[人]
        oldest.append(top_age)
    return oldest


def 余った子を配る(世帯番号, 世帯, 年齢の並び, 子ども数, 乱数):
    oldest = 各世帯の最年長(世帯, 年齢の並び)
    for 年齢 in range(len(子ども数)):
        for 子 in 子ども数[年齢]:
            possible = []
            for 世帯番号 in range(len(世帯)):
                if oldest[世帯番号] >= 年齢 + PARENT_MIN_GAP:
                    possible.append(世帯番号)
            if len(possible) == 0:
                世帯番号 = int(乱数.integers(len(世帯)))
            else:
                世帯番号 = possible[int(乱数.integers(len(possible)))]
            世帯番号[子] = 世帯番号
            世帯[世帯番号].append(子)


def 世帯を作る(年齢の並び, 性別の並び, household_types, 乱数):
    総数 = len(年齢の並び)

    世帯番号 = []
    for 人 in range(総数):
        世帯番号.append(NOBODY)

    子ども数 = 空の名簿()
    男の名簿 = 空の名簿()
    女の名簿 = 空の名簿()

    for shuffled in 乱数.permutation(総数):
        人 = int(shuffled)
        年齢 = 年齢の並び[人]
        if 年齢 < 成人年齢:
            子ども数[年齢].append(人)
        elif 性別の並び[人] == 男:
            男の名簿[年齢].append(人)
        else:
            女の名簿[年齢].append(人)

    kinds = list(household_types.keys())
    確率の並び = list(household_types.values())

    世帯 = []
    while 名簿の人数(男の名簿) + 名簿の人数(女の名簿) > 0:
        種類 = kinds[確率で選ぶ(確率の並び, 乱数)]
        構成員 = 世帯を組む(種類, 年齢の並び, 子ども数, 男の名簿, 女の名簿, 乱数)

        if len(構成員) == 0:
            人 = 大人を取る(男の名簿, 女の名簿, 成人年齢, 最高齢, 乱数)
            if 人 == NOBODY:
                break
            構成員 = [人]

        for 人 in 構成員:
            世帯番号[人] = len(世帯)
        世帯.append(構成員)

    余った子を配る(世帯番号, 世帯, 年齢の並び, 子ども数, 乱数)
    return 世帯番号, len(世帯)


def 企業の業種を決める(spend_share, 企業数):
    業種の並び = []
    for index in range(len(品目一覧)):
        how_many = round(spend_share[品目一覧[index]] * 企業数)
        for step in range(how_many):
            業種の並び.append(index)
    while len(業種の並び) > 企業数:
        業種の並び.pop()
    while len(業種の並び) < 企業数:
        業種の並び.append(len(品目一覧) - 1)
    return 業種の並び


PARENT_MIN_GAP_YEARS = 22
PARENT_MAX_GAP_YEARS = 45


def 親子の線を張る(国, 乱数):
    世帯 = 国.世帯
    head = 世帯.世帯主年齢

    並び順 = np.argsort(head)
    sorted_head = head[並び順]

    年上 = head.astype(np.int32)
    下 = np.searchsorted(sorted_head, 年上 + PARENT_MIN_GAP_YEARS, "left")
    上 = np.searchsorted(sorted_head, 年上 + PARENT_MAX_GAP_YEARS, "right")

    幅 = 上 - 下
    親世帯 = np.arange(世帯.総数, dtype=np.int32)
    見つかった = 幅 > 0
    if 見つかった.any():
        くじ = 乱数.random(世帯.総数)
        位置 = 下 + (くじ * np.maximum(幅, 1)).astype(np.int64)
        位置 = np.clip(位置, 0, 世帯.総数 - 1)
        親世帯[見つかった] = 並び順[位置[見つかった]].astype(np.int32)

    国.個人.出生世帯[:] = 親世帯[国.個人.世帯番号]


def 人口を生成する(初期データ, 乱数, 総数) -> 国家:

    assert len(初期データ["population"]["ages"]) == 最高齢 + 1

    企業数 = 既定設定["企業数"]

    年齢の並び, 性別の並び = 年齢と性別を作る(初期データ, 乱数, 総数)
    就業状態 = 就業状態を作る(年齢の並び, 性別の並び, 乱数)
    賃金の並び = 賃金を作る(賃金帯を読む(初期データ["wageByAge"]), 年齢の並び, 就業状態, 乱数)
    世帯番号, 世帯数 = 世帯を作る(年齢の並び, 性別の並び, 初期データ["householdTypes"], 乱数)

    国 = 国を用意する(総数, 世帯数, 企業数)
    人々 = 国.個人
    世帯 = 国.世帯
    企業 = 国.企業

    for 人 in range(総数):
        人々.年齢[人] = 年齢の並び[人]
        人々.性別[人] = 性別の並び[人]
        人々.就業状態[人] = 就業状態[人]
        人々.月給[人] = 賃金の並び[人]
        人々.世帯番号[人] = 世帯番号[人]
        人々.出生世帯[人] = 世帯番号[人]
        if 就業状態[人] == 就業:
            人々.基準労働時間[人] = FULL_TIME_HOURS
        人々.労働時間[人] = 人々.基準労働時間[人]

    home_of = 人々.世帯番号
    wages_yen = np.rint(人々.月給).astype(np.int64)

    世帯.世帯人員[:] = np.bincount(home_of, minlength=世帯数)
    世帯.子ども数[:] = np.bincount(
        home_of, weights=(人々.年齢 < 成人年齢), minlength=世帯数
    )
    世帯.所得[:] = np.rint(
        np.bincount(home_of, weights=wages_yen, minlength=世帯数)
    ).astype(np.int64)

    np.maximum.at(世帯.世帯主年齢, home_of, 人々.年齢)

    基準 = np.zeros(世帯数, dtype=np.float64)
    for upper, wealth in reversed(年齢別資産):
        基準[世帯.世帯主年齢 <= upper] = wealth

    mean_income = max(世帯.所得.mean(), 1.0)
    相対 = np.clip(世帯.所得 / mean_income, 0.2, 3.0)

    ばらつき = 乱数.lognormal(-資産のばらつき * 資産のばらつき / 2, 資産のばらつき, 世帯数)

    世帯.貯蓄[:] = np.rint(基準 * (0.4 + 0.6 * 相対) * ばらつき).astype(np.int64)

    業種の並び = 企業の業種を決める(初期データ["spendShare"], 企業数)
    for 企業番号 in range(企業数):
        企業.業種[企業番号] = 業種の並び[企業番号]

    firms_in_sector = []
    for index in range(len(品目一覧)):
        firms_in_sector.append([])
    for 企業番号 in range(企業数):
        firms_in_sector[業種の並び[企業番号]].append(企業番号)

    sector_chances = []
    for name in 品目一覧:
        sector_chances.append(初期データ["spendShare"][name])

    for 人 in range(総数):
        if 就業状態[人] == 就業:
            業種 = 確率で選ぶ(sector_chances, 乱数)
            choices = firms_in_sector[業種]
            企業番号 = choices[int(乱数.integers(len(choices)))]
            人々.勤務先[人] = 企業番号
            企業.資本[企業番号] = 企業.資本[企業番号] + 賃金の並び[人] * FIRM_CAPITAL_MONTHS

    親子の線を張る(国, 乱数)

    assert len(国.個人.年齢) == 総数
    assert 国.個人.世帯番号.min() >= 0
    assert len(np.unique(国.個人.世帯番号)) == 国.世帯.総数

    return 国


if __name__ == "__main__":
    人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])
