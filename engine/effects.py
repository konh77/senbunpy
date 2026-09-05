import numpy as np

from engine.params import 品目一覧

対応プリミティブ = ("税率変更", "給付", "禁止")


def 対応しているか(命令: dict) -> bool:
    return 命令.get("種別") in 対応プリミティブ


def 施行月(命令: dict, 慣らし月数: int) -> int:
    return 慣らし月数 + int(命令.get("施行", {}).get("月数", 0))


def 最初の施行月(法律の命令列, 慣らし月数: int):
    if not 法律の命令列:
        return None
    return min(施行月(命令, 慣らし月数) for 命令 in 法律の命令列)


def 施行済みを適用(法律の命令列, 国, base_p: dict, 慣らし月数: int):
    設定 = dict(base_p)
    設定["品目別消費税率"] = {}
    設定["所得税上乗せ"] = 0.0
    設定["相続税上乗せ"] = 0.0
    設定["相続税控除"] = None

    if not 法律の命令列:
        return 設定, []

    有効な法律 = [命令 for 命令 in 法律の命令列
              if 対応しているか(命令) and 国.経過月 >= 施行月(命令, 慣らし月数)]

    for 命令 in 有効な法律:
        if 命令["種別"] == "税率変更":
            税率を差し替える(命令, 設定)
        if 命令["種別"] == "給付" and 命令.get("財源"):
            財源を適用(命令["財源"], 設定)

    return 設定, 有効な法律


def 税率を差し替える(命令: dict, 設定: dict) -> None:
    if 命令["税"] == "消費税":
        if 命令["品目"] is None:
            設定["消費税率"] = 命令["変更後"]
        else:
            設定["品目別消費税率"][命令["品目"]] = 命令["変更後"]
    elif 命令["税"] == "所得":
        設定["所得税上乗せ"] += 命令["変更後"] - 命令["変更前"]
    elif 命令["税"] == "相続税":
        if 命令["品目"] == "基礎控除":
            設定["相続税控除"] = 命令["変更後"]
        else:
            設定["相続税上乗せ"] += 命令["変更後"] - 命令["変更前"]


def 財源を適用(財源指定: dict, 設定: dict) -> None:
    if 財源指定["種別"] != "税率変更":
        return
    if 財源指定["税"] == "所得":
        設定["所得税上乗せ"] += 財源指定["delta"]
    elif 財源指定["税"] == "消費税":
        設定["消費税率"] = 設定["消費税率"] + 財源指定["delta"]


def 対象世帯の印(対象指定: dict, 国) -> np.ndarray:
    世帯 = 国.世帯
    if 対象指定 is None:
        return np.ones(世帯.総数, dtype=bool)

    if 対象指定["対象種別"] == "世帯":
        return 条件を印に変える(対象指定, 世帯の属性表(国), 世帯.総数)

    if 対象指定["対象種別"] == "人":
        person_mask = 条件を印に変える(対象指定, 個人の属性表(国), 国.個人.総数)
        hit = np.bincount(国.個人.世帯番号, weights=person_mask, minlength=世帯.総数)
        return hit > 0

    return np.zeros(世帯.総数, dtype=bool)


def 世帯の属性表(国) -> dict:
    世帯 = 国.世帯
    return {"子ども数": 世帯.子ども数, "世帯人員": 世帯.世帯人員,
            "所得": 世帯.所得, "貯蓄": 世帯.貯蓄}


def 個人の属性表(国) -> dict:
    return {"年齢": 国.個人.年齢, "所得": 国.個人.月給}


比較の関数 = {"<": np.less, ">": np.greater, "<=": np.less_equal,
           ">=": np.greater_equal, "==": np.equal, "!=": np.not_equal}


def 条件を印に変える(対象指定: dict, columns: dict, 総数: int) -> np.ndarray:
    印 = np.ones(総数, dtype=bool)
    joins = 対象指定.get("接続", [])

    for index, (属性, 演算子, value) in enumerate(対象指定.get("条件", [])):
        column = columns.get(属性)
        if column is None:
            continue
        one = 比較の関数[演算子](column, value)
        if index == 0:
            印 = one
        elif joins[index - 1] == "または":
            印 = 印 | one
        else:
            印 = 印 & one
    return 印


def 給付を配る(有効な法律, 国, 台帳, 設定: dict) -> np.ndarray:
    世帯 = 国.世帯
    合計 = np.zeros(世帯.総数, dtype=np.int64)

    for 命令 in 有効な法律:
        if 命令["種別"] != "給付":
            continue

        印 = 対象世帯の印(命令.get("対象"), 国)
        額 = 命令["額"]

        per_household = np.full(世帯.総数, 額["値"], dtype=np.int64)
        if 額["掛ける対象"] is not None:
            column = 世帯の属性表(国).get(額["掛ける対象"])
            if column is not None:
                per_household = per_household * column.astype(np.int64)
        if 額["期間"] == "年":
            per_household = per_household // 12

        合計 += np.where(印, per_household, 0).astype(np.int64)

    if 合計.any():
        台帳.一括送金("政府", "家計", 合計, "給付")
        世帯.所得 += 合計
        世帯.貯蓄 += 合計

    return 合計


def 禁止を適用(有効な法律, 国, 支出: np.ndarray, 設定: dict) -> np.ndarray:

    for 命令 in 有効な法律:
        if 命令["種別"] != "禁止":
            continue

        対象 = 命令["内容"]
        if 対象["品目"] not in 品目一覧:
            continue
        桁 = 品目一覧.index(対象["品目"])

        印 = 対象世帯の印(命令.get("対象"), 国)
        取り分 = 1.0 if 対象["内数"] is None else 対象["内数"]
        target_spend = 支出[:, 桁] * 取り分

        if 対象["演算子"] in (">", ">="):
            excess = np.maximum(target_spend - 対象["値"], 0.0)
        else:
            excess = target_spend
        excess = np.where(印, excess, 0.0)

        enforcement = float(命令["執行率"])
        # 執行率のぶんだけ守られる。残りはそのまま買われ、消費税もかかる。
        支出[:, 桁] -= np.rint(excess * enforcement).astype(np.int64)

    np.maximum(支出, 0, out=支出)
