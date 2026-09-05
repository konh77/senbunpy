from pathlib import Path

import pytest

from dsl.parser import 実装済みの効果
from dsl.validator import 対象ごとの属性, 税の一覧
from engine.params import 品目一覧

PAGE = (Path(__file__).resolve().parent.parent / "web" / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("品目", 品目一覧)
def test_every_category_is_documented(品目):
    assert 品目 in PAGE


@pytest.mark.parametrize("対象種別,attrs", list(対象ごとの属性.items()))
def test_every_attribute_is_documented(対象種別, attrs):
    assert 対象種別 in PAGE
    for 属性 in attrs:
        assert 属性 in PAGE, f"{対象種別} の属性「{属性}」がサイトに載っていない"


@pytest.mark.parametrize("税", sorted(税の一覧))
def test_every_tax_is_documented(税):
    assert 税 in PAGE


@pytest.mark.parametrize("効果ひとつ", 実装済みの効果)
def test_every_effect_is_documented(効果ひとつ):
    assert 効果ひとつ in PAGE




def test_examples_on_the_page_actually_parse():
    import html as html_module
    import re

    from dsl.compiler import 法律を翻訳する
    from dsl.parser import 解析する
    from dsl.validator import 検証する

    block = re.search(r"<pre>(法律[\s\S]*?)</pre>", PAGE, re.IGNORECASE)
    assert block, "文法の例文が <pre> に見つからない"

    source = html_module.unescape(block.group(1))
    法律文 = 解析する(source)
    検証する(法律文)
    assert 法律を翻訳する(法律文)
