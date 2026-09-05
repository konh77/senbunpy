import numpy as np
import pytest
from numpy.random import default_rng

from engine.income import 所得フェーズ
from engine.init_pop import 人口を生成する, 初期データを読む
from engine.ledger import 会計台帳
from engine.metrics import 物価指数, ジニ係数, 失業率
from engine.params import 就業, 既定設定, 退職, 学生, 失業
from engine.state import 国を用意する


def test_gini_perfect_equality():
    assert ジニ係数(np.array([5, 5, 5, 5])) == 0.0


def test_gini_max_inequality():
    assert ジニ係数(np.array([0, 0, 0, 10])) == 0.75


def test_gini_all_zero_does_not_divide_by_zero():
    assert ジニ係数(np.array([0, 0, 0])) == 0.0


def test_gini_does_not_overflow_on_yen():
    x = np.full(100_000, 5_000_000, dtype=np.int64)
    assert ジニ係数(x) == pytest.approx(0.0, abs=1e-9)


def test_gini_of_generated_population():
    国 = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])
    所得フェーズ(国, 会計台帳(), 既定設定)

    g = ジニ係数(国.世帯.所得)
    assert 0.33 <= g <= 0.43, f"ジニ {g:.4f} が想定レンジ外"


def test_unemployment_denominator():
    国 = 国を用意する(6, 1, 1)
    国.個人.就業状態[:] = [
        就業, 就業, 就業, 失業, 学生, 退職,
    ]
    assert 失業率(国) == 0.25


def test_cpi_base_is_one():
    価格 = np.ones(8)
    q0 = np.array([3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0])
    assert 物価指数(価格, q0, np.ones(8)) == 1.0


def test_cpi_moves_with_prices():
    q0 = np.array([1.0, 1.0])
    価格 = np.array([1.1, 1.0])
    assert 物価指数(価格, q0, np.ones(2)) == pytest.approx(1.05)
