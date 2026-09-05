import numpy as np
import pytest

from dsl.compiler import 法律を翻訳する
from dsl.parser import 解析する
from engine.effects import 対応プリミティブ, 施行月, 対象世帯の印, 対応しているか
from engine.engine import 走らせる
from engine.params import 既定設定

MONTHS = 30
LAST = MONTHS - 1


def 系列(name_or_ir, 鍵):
    法律の命令列 = name_or_ir
    if isinstance(name_or_ir, str):
        原文 = open(f"laws/{name_or_ir}.law", encoding="utf-8").read()
        法律の命令列 = 法律を翻訳する(解析する(原文))
    return 走らせる(MONTHS, 乱数の種=42, 法律の命令列=法律の命令列)["系列"][鍵]


@pytest.fixture(scope="module")
def baseline():
    return 走らせる(MONTHS, 乱数の種=42)


def test_supported_is_the_single_source_of_truth():
    from dsl.validator import 節とIRの対応

    assert set(節とIRの対応.values()) == set(対応プリミティブ)
    assert 対応しているか({"種別": "税率変更"})
    assert not 対応しているか({"種別": "MANDATE"})


def test_law_does_nothing_before_enactment(baseline):
    命令 = 法律を翻訳する(解析する('法律 "x" { 効果 { 給付: 50000円/月 }\n 施行: 6ヶ月後 }'))
    treated = 走らせる(MONTHS, 乱数の種=42, 法律の命令列=命令)

    fire = 施行月(命令[0], 既定設定["慣らし月数"])
    assert fire == 既定設定["慣らし月数"] + 6

    for 鍵 in ("GDP", "所得ジニ", "政府債務"):
        assert baseline["系列"][鍵][:fire] == treated["系列"][鍵][:fire]
        assert baseline["系列"][鍵][fire] != treated["系列"][鍵][fire]


def test_params_are_not_mutated_between_runs(baseline):
    命令 = 法律を翻訳する(解析する('法律 "x" { 効果 { 税率変更: 消費税 10% -> 25% } }'))
    走らせる(MONTHS, 乱数の種=42, 法律の命令列=命令)

    assert 走らせる(MONTHS, 乱数の種=42) == baseline
    assert 既定設定["消費税率"] == 0.1


def test_rate_change_does_not_accumulate():
    from engine.effects import 施行済みを適用
    from engine.state import 国を用意する

    命令 = 法律を翻訳する(解析する(
        '法律 "x" { 効果 { 給付: 10000円/月 }\n 財源: 所得税(+1%) }'))
    国 = 国を用意する(1, 1, 1)
    国.経過月 = 既定設定["慣らし月数"] + 100

    最初, _ = 施行済みを適用(命令, 国, 既定設定, 既定設定["慣らし月数"])
    again, _ = 施行済みを適用(命令, 国, 既定設定, 既定設定["慣らし月数"])

    assert 最初["所得税上乗せ"] == 0.01
    assert again["所得税上乗せ"] == 0.01
    assert 既定設定.get("所得税上乗せ") is None


def test_household_mask_person_condition():
    from numpy.random import default_rng

    from engine.init_pop import 人口を生成する, 初期データを読む

    国 = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])

    kids = 対象世帯の印(
        {"対象種別": "人", "条件": [["年齢", "<", 18]], "接続": []}, 国)
    has_children = 国.世帯.子ども数 >= 1

    np.testing.assert_array_equal(kids, has_children)


def test_tax_rate_change_moves_revenue(baseline):
    up = 系列(法律を翻訳する(解析する('法律 "x" { 効果 { 税率変更: 消費税 10% -> 20% } }')),
                "財政収支")
    assert up[LAST] > baseline["系列"]["財政収支"][LAST]


def test_food_tax_cut_reduces_regressivity(baseline):
    cut = 系列("消費税改正法", "消費税の逆進性")
    base_reg = baseline["系列"]["消費税の逆進性"][LAST]

    assert base_reg > 1.3
    assert cut[LAST] < base_reg - 0.05

    base_gini = baseline["系列"]["所得ジニ"][LAST]
    moved = abs(系列("消費税改正法", "所得ジニ")[LAST] - base_gini) / base_gini
    assert moved < 0.001, "所得ジニで消費税の逆進性は測れない、が前提"


def test_transfer_lowers_gini_and_raises_debt(baseline):
    treated = 走らせる(MONTHS, 乱数の種=42, 法律の命令列=法律を翻訳する(解析する(
        open("laws/こども未来給付法.law", encoding="utf-8").read())))

    assert treated["系列"]["所得ジニ"][LAST] < baseline["系列"]["所得ジニ"][LAST]
    assert treated["系列"]["政府債務"][LAST] > baseline["系列"]["政府債務"][LAST]


def test_transfer_only_reaches_the_target():
    from numpy.random import default_rng

    from engine.effects import 給付を配る
    from engine.init_pop import 人口を生成する, 初期データを読む
    from engine.ledger import 会計台帳

    国 = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])
    台帳 = 会計台帳()
    命令 = 法律を翻訳する(解析する(open("laws/こども未来給付法.law", encoding="utf-8").read()))

    got = 給付を配る(命令, 国, 台帳, 既定設定)

    childless = 国.世帯.子ども数 == 0
    assert (got[childless] == 0).all()
    np.testing.assert_array_equal(
        got[~childless], 15000 * 国.世帯.子ども数[~childless].astype(np.int64))
    台帳.送金("家計", "政府", int(got.sum()), "test")
    台帳.保存則を検算()


def test_prohibition_reduces_spending_and_tax(baseline):
    """禁止すると、その支出が消えて **税収も減る**。

    どこにも「税収を減らせ」とは書いていない。買われなくなった分の
    消費税が入らなくなる、というだけ。
    """
    treated = 走らせる(MONTHS, 乱数の種=42, 法律の命令列=法律を翻訳する(解析する(
        open("laws/若者娯楽規制法.law", encoding="utf-8").read())))

    assert treated["系列"]["財政収支"][LAST] < baseline["系列"]["財政収支"][LAST]
    assert treated["系列"]["GDP"][LAST] < baseline["系列"]["GDP"][LAST]


def test_enforcement_rate_scales_the_effect(baseline):
    """執行率が高いほど効果が大きい。**執行率が効いていることの確認。**"""
    def 収支(執行率):
        命令 = 法律を翻訳する(解析する(
            '法律 "x" { 対象: 人 where 年齢 < 18\n'
            '  効果 { 禁止: 支出(カテゴリ=教養娯楽) > 1000円/月 }\n'
            f'  執行率: {執行率}% }}'))
        return 走らせる(MONTHS, 乱数の種=42, 法律の命令列=命令)["系列"]["財政収支"][LAST]

    ゆるい = 収支(20)
    きびしい = 収支(100)
    基準 = baseline["系列"]["財政収支"][LAST]

    assert 基準 > ゆるい > きびしい


def test_conservation_holds_with_every_example_law():
    for name in ("こども未来給付法", "消費税改正法", "若者娯楽規制法"):
        原文 = open(f"laws/{name}.law", encoding="utf-8").read()
        走らせる(MONTHS, 乱数の種=42, 法律の命令列=法律を翻訳する(解析する(原文)))


def test_handwritten_ir_gives_same_result():
    handwritten = [{
        "種別": "給付",
        "対象": {"対象種別": "世帯", "条件": [["子ども数", ">=", 1]], "接続": []},
        "額": {"値": 15000, "期間": "月", "掛ける対象": "子ども数"},
        "財源": {"種別": "税率変更", "税": "所得", "delta": 0.01},
        "施行": {"月数": 0},
    }]
    compiled = 法律を翻訳する(解析する(
        open("laws/こども未来給付法.law", encoding="utf-8").read()))

    assert 走らせる(MONTHS, 乱数の種=42, 法律の命令列=handwritten) == \
           走らせる(MONTHS, 乱数の種=42, 法律の命令列=compiled)


def test_inheritance_deduction_matters_more_than_the_rate(baseline):
    def revenue(原文):
        法律文 = 解析する(原文)
        return sum(走らせる(60, 乱数の種=42, 法律の命令列=法律を翻訳する(法律文))["系列"]["相続税収"])

    基準 = sum(baseline["系列"]["相続税収"])
    rate_up = revenue('法律 "x" { 効果 { 税率変更: 相続税 10% → 30% } }')
    deduction_down = revenue(
        '法律 "x" { 効果 { 税率変更: 相続税(基礎控除) 4200万円 → 1000万円 } }')

    assert rate_up > 基準
    assert deduction_down > rate_up, "控除の縮小のほうが税率引き上げより効くはず"


def test_inheritance_tax_is_small_either_way(baseline):
    inheritance = sum(baseline["系列"]["相続税収"])
    利子 = sum(baseline["系列"]["利払い"])
    assert 0 < inheritance < 利子


def test_inheritance_moves_no_money_between_sectors():
    import numpy as np
    from numpy.random import default_rng

    from engine.demography import 生命表などを作る, 人口フェーズ
    from engine.init_pop import 人口を生成する, 初期データを読む
    from engine.ledger import 会計台帳

    初期データ = 初期データを読む()
    乱数 = default_rng(42)
    国 = 人口を生成する(初期データ, 乱数, 既定設定["人口"])
    国.個人.年齢[:] = 109
    台帳 = 会計台帳()
    設定 = dict(既定設定, 相続税上乗せ=0.0, 相続税控除=0)

    変更前 = int(国.世帯.貯蓄.sum())
    人口フェーズ(国, 台帳, 乱数, 設定, 生命表などを作る(初期データ))
    変更後 = int(国.世帯.貯蓄.sum())

    税 = 台帳.名目別.get("相続税", 0) + 台帳.名目別.get("国庫帰属", 0)
    assert 税 > 0
    assert 変更前 - 変更後 == 税
    台帳.保存則を検算()


def test_births_do_not_keep_up_with_deaths(baseline):
    pop = baseline["系列"]["人口"]
    assert sum(baseline["系列"]["出生数"]) > 0
    assert sum(baseline["系列"]["死亡数"]) > sum(baseline["系列"]["出生数"])
    assert pop[-1] < pop[0]


def test_inheritance_needs_someone_to_have_left_home():
    from numpy.random import default_rng

    from engine.init_pop import 人口を生成する, 初期データを読む

    国 = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])
    own_home = 国.個人.出生世帯 == 国.個人.世帯番号

    assert not own_home.all()
