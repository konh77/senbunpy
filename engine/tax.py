import numpy as np

from engine.params import 品目一覧

UPPER = np.array([1950000, 3300000, 6950000, 9000000,
                  18000000, 40000000, np.inf])
RATE = np.array([0.05, 0.10, 0.20, 0.23, 0.33, 0.40, 0.45])
DEDUCT = np.array([0, 97500, 427500, 636000, 1536000, 2796000, 4796000])

BASIC_DEDUCTION = 580000

SALARY_RATE = 0.7


def 所得税年額(課税所得額, add=0.0):
    i = np.searchsorted(UPPER, 課税所得額, side="right")

    税 = 課税所得額 * (RATE[i] + add) - DEDUCT[i]
    税 = np.maximum(税, 0)
    return np.rint(税).astype(np.int64)


def 課税所得(annual):
    課税所得額 = annual * SALARY_RATE - BASIC_DEDUCTION
    課税所得額 = np.maximum(課税所得額, 0)
    return np.rint(課税所得額).astype(np.int64)


def 消費税率(設定):
    税率の並び = np.full(len(品目一覧), 設定["消費税率"])
    税率の並び[品目一覧.index("食料")] = 設定["軽減税率"]

    for name, 割合 in 設定.get("品目別消費税率", {}).items():
        税率の並び[品目一覧.index(name)] = 割合

    return 税率の並び


def 品目別消費税(額面, 税率の並び):
    shouhizei = 額面 * 税率の並び / (1.0 + 税率の並び)
    return np.rint(shouhizei).astype(np.int64)


SOUZOKU_UPPER = np.array([10_000_000, 30_000_000, 50_000_000, 100_000_000,
                          200_000_000, 300_000_000, 600_000_000, np.inf])
SOUZOKU_RATE = np.array([0.10, 0.15, 0.20, 0.30, 0.40, 0.45, 0.50, 0.55])
SOUZOKU_DEDUCT = np.array([0, 500_000, 2_000_000, 7_000_000,
                           17_000_000, 27_000_000, 42_000_000, 72_000_000])

SOUZOKU_BASE = 30_000_000
SOUZOKU_PER_HEIR = 6_000_000


def 相続税の基礎控除(相続人たち: int, 設定=None) -> int:
    if 設定 is not None and 設定.get("相続税控除") is not None:
        return int(設定["相続税控除"])
    return SOUZOKU_BASE + SOUZOKU_PER_HEIR * 相続人たち


def 相続税額(遺産, 相続人たち: int = 2, add: float = 0.0, 設定=None):
    遺産 = np.asarray(遺産, dtype=np.float64)
    控除 = 相続税の基礎控除(相続人たち, 設定)

    課税所得額 = np.maximum(遺産 - 控除, 0.0)
    per_heir = 課税所得額 / max(相続人たち, 1)

    i = np.searchsorted(SOUZOKU_UPPER, per_heir, side="right")
    tax_each = per_heir * (SOUZOKU_RATE[i] + add) - SOUZOKU_DEDUCT[i]
    tax_each = np.maximum(tax_each, 0.0)

    合計 = tax_each * max(相続人たち, 1)
    合計 = np.minimum(合計, 遺産)
    return np.rint(合計).astype(np.int64)
