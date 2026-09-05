import numpy as np
import pytest

from engine.ledger import 会計台帳


def test_transfer_moves_money():
    台帳 = 会計台帳()
    台帳.送金("家計", "政府", 100, "test")

    assert 台帳.今月の増減["家計"] == -100
    assert 台帳.今月の増減["政府"] == 100
    assert 台帳.名目別["test"] == 100

    assert 台帳.今月の増減["企業"] == 0
    assert 台帳.今月の増減["外部"] == 0

    台帳.保存則を検算()


def test_float_amount_raises():
    台帳 = 会計台帳()

    with pytest.raises(TypeError):
        台帳.送金("家計", "政府", 100.0, "x")

    with pytest.raises(TypeError):
        台帳.送金("家計", "政府", np.float64(100.0), "x")

    assert 台帳.今月の増減["家計"] == 0
    assert 台帳.今月の増減["政府"] == 0
    assert 台帳.名目別 == {}


def test_negative_amount_raises():
    台帳 = 会計台帳()

    with pytest.raises(ValueError):
        台帳.送金("家計", "政府", -100, "x")

    assert 台帳.今月の増減["家計"] == 0


def test_unknown_account_raises():
    台帳 = 会計台帳()

    with pytest.raises(ValueError):
        台帳.送金("HOUSEHOLD", "政府", 100, "x")

    with pytest.raises(ValueError):
        台帳.送金("家計", "GOVERNMENT", 100, "x")


def test_zero_is_allowed():
    台帳 = 会計台帳()
    台帳.送金("外部", "家計", 0, "賃金")

    assert 台帳.今月の増減["家計"] == 0
    assert 台帳.名目別["賃金"] == 0


def test_conservation_detects_a_fake_bug():
    台帳 = 会計台帳()
    台帳.送金("家計", "政府", 100, "test")
    台帳.保存則を検算()

    台帳.今月の増減["政府"] += 100

    with pytest.raises(AssertionError):
        台帳.保存則を検算()


def test_transfer_bulk_matches_sum():
    amounts = np.array([100, 200, 300], dtype=np.int64)

    bulk = 会計台帳()
    bulk.一括送金("外部", "家計", amounts, "賃金")

    single = 会計台帳()
    single.送金("外部", "家計", 600, "賃金")

    assert bulk.今月の増減 == single.今月の増減
    assert bulk.名目別 == single.名目別
    bulk.保存則を検算()


def test_transfer_bulk_rejects_non_int64():
    台帳 = 会計台帳()

    with pytest.raises(TypeError):
        台帳.一括送金("外部", "家計", np.array([1.0, 2.0]), "賃金")

    with pytest.raises(TypeError):
        台帳.一括送金(
            "外部", "家計", np.array([1, 2], dtype=np.int32), "賃金"
        )

    with pytest.raises(TypeError):
        台帳.一括送金("外部", "家計", [1, 2, 3], "賃金")

    assert 台帳.今月の増減["家計"] == 0


def test_transfer_bulk_rejects_negative():
    台帳 = 会計台帳()
    amounts = np.array([100, -1, 300], dtype=np.int64)

    with pytest.raises(ValueError):
        台帳.一括送金("外部", "家計", amounts, "賃金")

    assert 台帳.今月の増減["家計"] == 0


def test_transfer_bulk_empty_array():
    台帳 = 会計台帳()
    台帳.一括送金("政府", "家計", np.array([], dtype=np.int64), "給付")

    assert 台帳.今月の増減["政府"] == 0
    assert 台帳.名目別["給付"] == 0


def test_by_tag_accumulates_within_a_tick():
    台帳 = 会計台帳()
    台帳.送金("家計", "政府", 100, "所得税")
    台帳.送金("家計", "政府", 250, "所得税")
    台帳.送金("家計", "政府", 30, "消費税")

    assert 台帳.名目別["所得税"] == 350
    assert 台帳.名目別["消費税"] == 30


def test_close_tick_moves_delta_into_balance():
    台帳 = 会計台帳()
    台帳.送金("家計", "政府", 100, "所得税")
    台帳.月を締める()

    assert 台帳.残高["政府"] == 100
    assert 台帳.残高["家計"] == -100
    assert 台帳.今月の増減["政府"] == 0
    assert 台帳.今月の増減["家計"] == 0
    assert 台帳.名目別 == {}

    台帳.送金("家計", "政府", 50, "所得税")
    台帳.月を締める()
    assert 台帳.残高["政府"] == 150


def test_close_tick_refuses_to_close_a_broken_tick():
    台帳 = 会計台帳()
    台帳.今月の増減["政府"] += 100

    with pytest.raises(AssertionError):
        台帳.月を締める()

    assert 台帳.残高["政府"] == 0


def test_balances_always_sum_to_zero():
    台帳 = 会計台帳()
    for _ in range(12):
        台帳.送金("外部", "家計", 1_000_000, "賃金")
        台帳.送金("家計", "政府", 120_000, "所得税")
        台帳.送金("家計", "企業", 700_000, "消費")
        台帳.月を締める()

    assert sum(台帳.残高.values()) == 0
    assert 台帳.残高["家計"] == 12 * (1_000_000 - 120_000 - 700_000)
