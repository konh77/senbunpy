import numpy as np
import pytest
from numpy.random import default_rng

from engine.init_pop import 人口を生成する, 初期データを読む
from engine.params import 就業, 既定設定, 失業


@pytest.fixture(scope="module")
def pop():
    return 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])


def test_mean_age(pop):
    assert 46.0 <= pop.個人.年齢.mean() <= 50.0


def test_household_size(pop):
    assert 1.9 <= pop.世帯.世帯人員.mean() <= 2.4


def test_unemployment_share(pop):
    就業者 = int((pop.個人.就業状態 == 就業).sum())
    unemployed = int((pop.個人.就業状態 == 失業).sum())
    割合 = unemployed / (就業者 + unemployed)
    assert 0.02 <= 割合 <= 0.04


def test_everyone_has_a_household(pop):
    home_of = pop.個人.世帯番号

    assert home_of.min() >= 0
    assert len(np.unique(home_of)) == pop.世帯.総数


def test_money_is_in_yen(pop):
    賃金の並び = pop.個人.月給
    earners = 賃金の並び[賃金の並び > 0]

    assert 200_000 < earners.mean() < 800_000
    assert pop.世帯.所得.dtype == np.int64
    assert pop.世帯.貯蓄.dtype == np.int64


@pytest.mark.skip(reason="出典の確認待ち。結論が出るまで期待レンジを書かない")
def test_wage_level_against_statistics():
    pass
