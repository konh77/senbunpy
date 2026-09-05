import json
from pathlib import Path

import pytest

from dsl.compiler import 法律を翻訳する, JSONにする
from dsl.errors import 法律エラー, 字句エラー, 範囲外エラー, 構文エラー, 検証エラー
from dsl.lexer import 字句に分ける
from dsl.parser import 解析する
from dsl.tokens import 字句種別
from dsl.validator import 検証する

LAWS = Path(__file__).resolve().parent.parent / "laws"
EXAMPLES = ("こども未来給付法", "消費税改正法", "若者娯楽規制法")


def source_of(name: str) -> str:
    return (LAWS / f"{name}.law").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", EXAMPLES)
def test_tokenize_three_examples(name):
    字句列 = 字句に分ける(source_of(name))
    assert 字句列[0].type == 字句種別.KEYWORD and 字句列[0].値 == "法律"
    assert 字句列[-1].type == 字句種別.EOF
    assert all(t.行 >= 1 and t.桁 >= 1 for t in 字句列)


def test_fullwidth_space():
    half = 字句に分ける('法律 "x" { 効果 { 給付: 1000円/月 } }')
    full = 字句に分ける('法律　"x"　{　効果　{　給付:　1000円/月　}　}')

    assert [(t.type, t.値) for t in half] == [(t.type, t.値) for t in full]


def test_fullwidth_punctuation_is_accepted():
    法律文 = 解析する('法律 "x" ｛ 効果 ｛ 給付： １５０００円／月 ｝ ｝')
    assert 法律文.効果()[0].額.数 == 15000


def test_lex_error_has_position():
    with pytest.raises(字句エラー) as err:
        字句に分ける('法律 "x" {\n  効果 ※ 1\n}')

    assert err.value.行 == 2
    assert err.value.桁 == 6
    assert "※" in err.value.本文


def test_comments_are_skipped():
    for marker in ("//", "#"):
        法律文 = 解析する(f'{marker} これは注釈\n法律 "x" {{ 効果 {{ 給付: 1円/月 }} }}')
        assert 法律文.name == "x"


def test_unit_and_noun_are_distinguished_by_position():
    対象種別 = 字句に分ける("対象: 人")[2]
    counter = 字句に分ける("世帯人員 >= 3人")[3]

    assert 対象種別.type == 字句種別.IDENT
    assert counter.type == 字句種別.UNIT


@pytest.mark.parametrize("name", EXAMPLES)
def test_parse_three_examples(name):
    法律文 = 解析する(source_of(name))
    assert 法律文.name == name
    assert 法律文.効果()


def test_parse_keeps_positions():
    法律文 = 解析する('法律 "x" {\n  効果 {\n    給付: 1000円/月\n  }\n}')
    assert 法律文.効果()[0].行 == 3


@pytest.mark.parametrize("broken,無ければ叱る", [
    ('法律 "x" { 効果 { 給付: 1000円/月 }', "閉じられていません"),
    ('法律 "x" { 対象 人 }', "':' が必要です"),
    ('法律 "x" { 謎の節: 1 }', "読めません"),
    ('法律 "x" { 執行率: "高い" }', "数値が必要です"),
    ('法律 "x" { 効果 { } }', "効果が空です"),
])
def test_parse_errors_are_readable(broken, 無ければ叱る):
    with pytest.raises(構文エラー) as err:
        解析する(broken)

    assert 無ければ叱る in err.value.本文
    assert err.value.行 >= 1
    assert err.value.助言, "ヒントの無いエラーは半分の仕事しかしていない"
    assert "^" in str(err.value), "該当箇所を指す ^ が出ていない"


def test_infinite_loop_guard():
    with pytest.raises(法律エラー):
        解析する('法律 "x" { : }')


def test_transfer_without_funding_warns_not_fails():
    警告の並び = 検証する(解析する('法律 "x" { 効果 { 給付: 20000円/月 } }'))

    text = "\n".join(str(w) for w in 警告の並び)
    assert "財源が指定されていません" in text
    assert "国債" in text
    assert "金利" in text


def test_funding_is_not_warned_when_given():
    assert not any("財源が指定されていません" in str(w)
                   for w in 検証する(解析する(source_of("こども未来給付法"))))


@pytest.mark.parametrize("法律文,missing", [
    ('法律 "x" { 効果 { 外交: 1 } }', "国外"),
    ('法律 "x" { 憲法改正: 1 }', "統治機構"),
    ('法律 "x" { 効果 { 義務: 有給取得 } }', "仕組みがありません"),
    ('法律 "x" { 効果 { 税率変更: 酒税 10% -> 20% } }', "存在しない税"),
    ('法律 "x" { 対象: 世帯 where 幸福度 >= 1\n 効果 { 給付: 1円/月 } }', "属性"),
    ('法律 "x" { 効果 { 禁止: 支出(カテゴリ=宇宙旅行) > 1円/月 } }', "8分類"),
])
def test_out_of_scope_is_refused_with_reason(法律文, missing):
    with pytest.raises(範囲外エラー) as err:
        検証する(解析する(法律文))

    assert missing in str(err.value)
    assert err.value.行 >= 1


@pytest.mark.parametrize("法律文,無ければ叱る", [
    ('法律 "x" { 対象: 人 where 年齢 < 18円\n 効果 { 給付: 1円/月 } }', "単位は「歳」"),
    ('法律 "x" { 効果 { 禁止: 支出(カテゴリ=食料) > 1円/月 }\n 執行率: 120% }', "0〜100%"),
    ('法律 "x" { 効果 { 税率変更: 消費税 10% -> 12 } }', "% で書きます"),
])
def test_type_errors(法律文, 無ければ叱る):
    with pytest.raises(検証エラー) as err:
        検証する(解析する(法律文))
    assert 無ければ叱る in str(err.value)


def test_double_taxation_warns():
    警告の並び = 検証する(解析する(
        '法律 "x" { 効果 { 税率変更: 消費税(食料品) 8% -> 5%\n'
        '                  税率変更: 消費品目違い 5% -> 3% } }'.replace("消費品目違い", "消費税(食料品)")
    ))
    assert any("2回変更" in str(w) for w in 警告の並び)


def test_subcategory_is_warned_not_silently_accepted():
    """統計に無い品目は **内数として通すが、黙って通さない。**

    例文では使っていないが、仕組みとしては生きている。
    黙って内数にすると「何を禁止したらそうなったか」が消えるので、必ず書く。
    """
    警告の並び = 検証する(解析する(
        '法律 "x" { 効果 { 禁止: 支出(カテゴリ=ガチャ) > 5000円/月 } }'))
    text = chr(10).join(str(w) for w in 警告の並び)

    assert "教養娯楽の内数" in text
    assert "設計値" in text and "出典はありません" in text


def test_compiled_ir_shape():
    命令 = 法律を翻訳する(解析する(source_of("こども未来給付法")))[0]

    assert 命令["種別"] == "給付"
    assert 命令["対象"] == {"対象種別": "世帯",
                            "条件": [["子ども数", ">=", 1]], "接続": []}
    assert 命令["額"] == {"値": 15000, "期間": "月", "掛ける対象": "子ども数"}
    assert 命令["財源"] == {"種別": "税率変更", "税": "所得", "delta": 0.01}


def test_category_stays_japanese_in_ir():
    命令 = 法律を翻訳する(解析する(source_of("消費税改正法")))
    assert 命令[0]["品目"] == "食料"
    assert 命令[0]["税"] == "消費税"
