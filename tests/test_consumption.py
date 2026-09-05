import numpy as np
import pytest
from numpy.random import default_rng

from engine.consumption import 基礎バスケットを作る, 消費フェーズ
from engine.income import 所得フェーズ
from engine.init_pop import 人口を生成する, 初期データを読む
from engine.ledger import 会計台帳
from engine.params import 品目一覧, 既定設定
from engine.state import 国を用意する


@pytest.fixture(scope="module")
def バスケット():
    初期データ = 初期データを読む()
    shares = np.array([初期データ["spendShare"][c] for c in 品目一覧])
    return 基礎バスケットを作る(shares, 既定設定)


def fresh_world():
    国 = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])
    return 国, 会計台帳()


def test_budget_identity(バスケット):
    国, 台帳 = fresh_world()
    基礎量, 限界配分 = バスケット

    savings_before = 国.世帯.貯蓄.copy()
    所得フェーズ(国, 台帳, 既定設定)
    所得 = 国.世帯.所得.copy()
    支出 = 消費フェーズ(国, 台帳, 既定設定, 基礎量, 限界配分)

    change = 国.世帯.貯蓄 - savings_before
    np.testing.assert_array_equal(支出.sum(axis=1) + change, 所得)


def test_conserves_with_consumption(バスケット):
    国, 台帳 = fresh_world()
    所得フェーズ(国, 台帳, 既定設定)
    消費フェーズ(国, 台帳, 既定設定, *バスケット)

    台帳.保存則を検算()
    assert 台帳.名目別["消費"] > 0
    assert 台帳.名目別["消費税"] > 0


def test_nobody_spends_money_they_do_not_have(バスケット):
    国, 台帳 = fresh_world()
    所得フェーズ(国, 台帳, 既定設定)
    消費フェーズ(国, 台帳, 既定設定, *バスケット)

    assert (国.世帯.貯蓄 >= 0).all()


def test_poor_household_proportional(バスケット):
    基礎量, 限界配分 = バスケット

    国 = 国を用意する(0, 2, 1)
    国.世帯.世帯人員[:] = [1, 1]
    国.世帯.所得[:] = [0, 20_000]
    国.世帯.貯蓄[:] = 国.世帯.所得

    支出 = 消費フェーズ(国, 会計台帳(), 既定設定, 基礎量, 限界配分)

    assert 国.世帯.困窮.all()
    assert 支出[0].sum() == 0
    assert 支出[1].sum() <= 20_000

    got = 支出[1] / 支出[1].sum()
    want = 基礎量 / 基礎量.sum()
    np.testing.assert_allclose(got, want, atol=0.01)


def test_les_asymmetry(バスケット):
    基礎量, 限界配分 = バスケット
    food = 品目一覧.index("食料")
    fun = 品目一覧.index("教養娯楽")

    def spend_at(scale):
        国, 台帳 = fresh_world()
        所得フェーズ(国, 台帳, 既定設定)
        国.世帯.所得[:] = (国.世帯.所得 * scale).astype(np.int64)
        国.世帯.貯蓄[:] = (国.世帯.貯蓄 * scale).astype(np.int64)
        return 消費フェーズ(国, 台帳, 既定設定, 基礎量, 限界配分).sum(axis=0)

    基準 = spend_at(1.0)
    poorer = spend_at(0.9)

    drop_food = 1.0 - poorer[food] / 基準[food]
    drop_fun = 1.0 - poorer[fun] / 基準[fun]

    assert drop_food < drop_fun
    print(f"\n所得10%減 → 食料 {drop_food:.1%} 減 / 教養娯楽 {drop_fun:.1%} 減")
