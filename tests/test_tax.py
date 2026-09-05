import numpy as np
import pytest

from engine.params import 品目一覧, 既定設定
from engine.tax import (
    UPPER,
    品目別消費税,
    所得税年額,
    消費税率,
    課税所得,
)


def test_income_tax_300man():
    税 = 所得税年額(np.array([3_000_000], dtype=np.int64))
    assert 税[0] == 202_500


def test_income_tax_700man():
    税 = 所得税年額(np.array([7_000_000], dtype=np.int64))
    assert 税[0] == 974_000


def test_all_brackets():
    課税所得額 = np.array(
        [1_000_000, 3_000_000, 5_000_000, 7_000_000,
         10_000_000, 20_000_000, 50_000_000],
        dtype=np.int64,
    )
    expected = np.array(
        [50_000, 202_500, 572_500, 974_000,
         1_764_000, 5_204_000, 17_704_000],
        dtype=np.int64,
    )
    assert (所得税年額(課税所得額) == expected).all()


def test_bracket_boundary():
    課税所得額 = np.array([1_949_999, 1_950_000, 1_950_001], dtype=np.int64)
    税 = 所得税年額(課税所得額)

    assert 税[0] == 97_500
    assert 税[1] == 97_500
    assert 税[2] == 97_500


def test_no_reversal_at_any_boundary():
    thresholds = UPPER[:-1].astype(np.int64)

    below = 所得税年額(thresholds - 1)
    at = 所得税年額(thresholds)

    assert (at >= below).all()
    assert (at - below <= 1).all()


def test_zero_and_negative_income():
    税 = 所得税年額(np.array([0, -1, -1_000_000], dtype=np.int64))
    assert (税 == 0).all()


def test_returns_int64():
    税 = 所得税年額(np.array([3_000_000], dtype=np.int64))
    assert 税.dtype == np.int64


def test_taxable_is_less_than_gross():
    annual = np.array([3_000_000, 5_000_000, 7_000_000], dtype=np.int64)
    課税所得額 = 課税所得(annual)

    assert 課税所得額.dtype == np.int64
    assert (課税所得額 < annual).all()
    assert (課税所得額 > 0).all()


def test_taxable_clips_to_zero():
    課税所得額 = 課税所得(np.array([0, 500_000], dtype=np.int64))
    assert (課税所得額 == 0).all()


def test_taxable_is_a_known_approximation():
    課税所得額 = 課税所得(np.array([1_000_000], dtype=np.int64))
    assert 課税所得額[0] == 120_000


def test_shouhizei_uchizei_formula():
    zei = 品目別消費税(np.array([1_100], dtype=np.int64), np.array([0.10]))
    assert zei[0] == 100


def test_shouhizei_is_not_the_naive_formula():
    zei = 品目別消費税(np.array([1_100], dtype=np.int64), np.array([0.10]))
    assert zei[0] != 110


def test_shouhizeiritu_follows_categories_order():
    税率の並び = 消費税率(既定設定)

    assert len(税率の並び) == len(品目一覧)
    assert 税率の並び[品目一覧.index("食料")] == 既定設定["軽減税率"]
    assert 税率の並び[品目一覧.index("教養娯楽")] == 既定設定["消費税率"]
    assert 税率の並び[品目一覧.index("住居")] == 既定設定["消費税率"]


def test_keigenzei_is_cheaper():
    税率の並び = 消費税率(既定設定)
    額面 = np.full(len(品目一覧), 10_000, dtype=np.int64)
    zei = 品目別消費税(額面, 税率の並び)

    assert zei.dtype == np.int64
    assert zei[品目一覧.index("食料")] < zei[品目一覧.index("その他")]


def test_shouhizeiritu_is_swappable():
    額面 = np.array([11_000], dtype=np.int64)

    at_10 = 品目別消費税(額面, np.array([0.10]))
    at_12 = 品目別消費税(額面, np.array([0.12]))

    assert at_10[0] == 1_000
    assert at_12[0] < 額面[0]
    assert at_12[0] > at_10[0]
