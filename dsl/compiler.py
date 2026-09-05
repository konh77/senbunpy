import json

from dsl.ast_nodes import (
    条件, 効果一覧, 執行率, 財源, 法律, 禁止,
    税率変更, 対象, 施行, 給付,
)
from dsl.validator import 金額で書く項目, 品目名をそろえる

対象種別の英訳 = {"人": "人", "世帯": "世帯", "企業": "企業"}

属性の英訳 = {
    "年齢": "年齢",
    "子ども数": "子ども数",
    "世帯人員": "世帯人員",
    "所得": "所得",
    "貯蓄": "貯蓄",
    "業種": "業種",
}

税の英訳 = {"消費税": "消費税", "所得税": "所得", "相続税": "相続税"}

期間の英訳 = {"月": "月", "年": "年", "ヶ月": "月", "か月": "月", "カ月": "月"}


def 法律を翻訳する(法律文: 法律) -> list:
    対象指定 = 対象を翻訳(法律文.節を探す(対象))
    timing = 施行を翻訳(法律文.節を探す(施行))
    enforcement = 執行率を翻訳(法律文.節を探す(執行率))
    財源指定 = 財源を翻訳(法律文.節を探す(財源))

    out = []
    for 効果ひとつ in 法律文.効果():
        命令 = None

        if isinstance(効果ひとつ, 税率変更):
            amount_field = (効果ひとつ.税, 効果ひとつ.品目) in 金額で書く項目
            品目 = 効果ひとつ.品目
            if not amount_field and 効果ひとつ.税 == "消費税":
                品目, _ = 品目名をそろえる(効果ひとつ.品目)
            命令 = {
                "種別": "税率変更",
                "税": 税の英訳[効果ひとつ.税],
                "品目": 品目,
                "unit": "yen" if amount_field else "rate",
                "変更前": 効果ひとつ.変更前.円にする() if amount_field else 効果ひとつ.変更前.割合にする(),
                "変更後": 効果ひとつ.変更後.円にする() if amount_field else 効果ひとつ.変更後.割合にする(),
            }

        elif isinstance(効果ひとつ, 給付):
            命令 = {
                "種別": "給付",
                "対象": 対象指定 or {"対象種別": "世帯", "条件": []},
                "額": {
                    "値": int(効果ひとつ.額.数),
                    "期間": 期間の英訳.get(効果ひとつ.期間, "月"),
                    "掛ける対象": 属性の英訳.get(効果ひとつ.掛ける対象) if 効果ひとつ.掛ける対象 else None,
                },
                "財源": 財源指定,
            }

        elif isinstance(効果ひとつ, 禁止):
            品目, 取り分 = 品目名をそろえる(効果ひとつ.引数.get("カテゴリ"))
            命令 = {
                "種別": "禁止",
                "対象": 対象指定 or {"対象種別": "人", "条件": []},
                "内容": {
                    "種類": "支出",
                    "品目": 品目,
                    "内数": 取り分,
                    "演算子": 効果ひとつ.演算子,
                    "値": int(効果ひとつ.上限.数) if 効果ひとつ.上限 else 0,
                    "期間": 期間の英訳.get(効果ひとつ.期間, "月"),
                },
                "執行率": 1.0 if enforcement is None else enforcement,
            }

        if 命令 is not None:
            命令["施行"] = timing
            命令["出典"] = {"法律": 法律文.name, "行": 効果ひとつ.行}
            out.append(命令)

    return out


def 対象を翻訳(対象指定: 対象 | None):
    if 対象指定 is None:
        return None
    return {
        "対象種別": 対象種別の英訳[対象指定.対象種別],
        "条件": 条件を翻訳(対象指定.条件),
        "接続": list(対象指定.条件.接続語) if 対象指定.条件 else [],
    }


def 条件を翻訳(条件: 条件 | None) -> list:
    if 条件 is None:
        return []
    return [[属性の英訳[c.属性], c.演算子, c.値.割合にする() if c.値.単位 == "%" else c.値.数]
            for c in 条件.比較の並び]


def 施行を翻訳(timing: 施行 | None) -> dict:
    return {"月数": timing.施行月数 if timing else 0}


def 執行率を翻訳(enforce: 執行率 | None):
    return enforce.割合.割合にする() if enforce else None


def 財源を翻訳(財源指定: 財源 | None):
    if 財源指定 is None:
        return None
    if 財源指定.種類 == "bond":
        return {"種別": "国債"}
    return {
        "種別": "税率変更",
        "税": 税の英訳[財源指定.税],
        "delta": 財源指定.今月の増減.割合にする() if 財源指定.今月の増減 else 0.0,
    }


def JSONにする(法律の命令列: list) -> str:
    return json.dumps(法律の命令列, ensure_ascii=False, indent=2)
