import numpy as np
import pytest
from numpy.random import default_rng

from engine.income import 所得フェーズ
from engine.init_pop import 人口を生成する, 初期データを読む
from engine.ledger import 会計台帳
from engine.params import 就業, 既定設定


@pytest.fixture
def world():
    国 = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])
    return 国, 会計台帳()


def test_bincount_by_hand():
    世帯番号 = np.array([0, 0, 1, 1, 1])
    手取り = np.array([100, 200, 30, 40, 50])

    got = np.bincount(世帯番号, weights=手取り, minlength=2)
    assert list(got) == [300.0, 120.0]

    assert got.dtype == np.float64

    short = np.bincount(np.array([0, 0, 1, 1]), minlength=0)
    assert len(short) == 2
    assert len(np.bincount(np.array([0, 0, 1, 1]), minlength=5)) == 5


def test_only_employed_earn(world):
    国, 台帳 = world
    所得フェーズ(国, 台帳, 既定設定)

    not_working = 国.個人.就業状態 != 就業
    assert (国.個人.月給[not_working] == 0).all()


def test_income_phase_conserves(world):
    国, 台帳 = world
    所得フェーズ(国, 台帳, 既定設定)

    台帳.保存則を検算()
    assert 台帳.名目別["賃金"] > 0
    assert 台帳.名目別["所得税"] > 0


def test_net_never_negative(world):
    国, 台帳 = world
    所得フェーズ(国, 台帳, 既定設定)

    assert (国.世帯.所得 >= 0).all()


def test_pension_reaches_the_old(world):
    国, 台帳 = world
    所得フェーズ(国, 台帳, 既定設定)
    with_pension = float((国.世帯.所得 == 0).mean())

    s2 = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])
    no_pension = dict(既定設定, 年金月額=0)
    所得フェーズ(s2, 会計台帳(), no_pension)
    without = float((s2.世帯.所得 == 0).mean())

    assert with_pension < 0.10
    assert without > 0.35
