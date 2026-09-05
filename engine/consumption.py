import numpy as np

from engine.effects import 禁止を適用
from engine.params import 品目一覧, 基礎割合
from engine.tax import 品目別消費税, 消費税率


def 基礎バスケットを作る(init_shares: np.ndarray, 設定: dict):
    subsistence = np.array([基礎割合[c] for c in 品目一覧])
    基礎量 = subsistence * init_shares * 設定["基準生活費"]
    限界配分 = init_shares * (1.0 - subsistence)
    return 基礎量, 限界配分 / 限界配分.sum()


def 等価人員(sizes: np.ndarray) -> np.ndarray:
    return np.sqrt(np.maximum(sizes, 1).astype(np.float64))


def 限界消費性向(所得: np.ndarray, 等価人数: np.ndarray, 設定: dict) -> np.ndarray:
    ratio = 所得 / (設定["基準生活費"] * 等価人数)
    return 設定["高所得の消費性向"] + (設定["低所得の消費性向"] - 設定["高所得の消費性向"]) / (1.0 + np.maximum(ratio, 0.0))


def 消費フェーズ(国, 台帳, 設定: dict, 基礎量: np.ndarray, 限界配分: np.ndarray,
                      有効な法律=None) -> np.ndarray:
    世帯 = 国.世帯
    価格 = 国.価格

    cash = 世帯.貯蓄
    所得 = 世帯.所得
    等価人数 = 等価人員(世帯.世帯人員)

    committed_by_cat = 等価人数[:, None] * 基礎量[None, :] * 価格[None, :]
    基礎バスケット代 = committed_by_cat.sum(axis=1)

    資力 = 所得 + 設定["貯蓄取崩率"] * (cash - 所得).clip(min=0)
    total_spend = 基礎バスケット代 + 限界消費性向(所得, 等価人数, 設定) * (資力 - 基礎バスケット代)
    total_spend = np.clip(total_spend, 0.0, cash.astype(np.float64))

    余り = total_spend - 基礎バスケット代
    支出 = committed_by_cat + 限界配分[None, :] * 余り[:, None]

    困窮 = 余り < 0.0
    scale = np.divide(total_spend, 基礎バスケット代,
                      out=np.zeros_like(total_spend), where=基礎バスケット代 > 0)
    支出 = np.where(困窮[:, None], committed_by_cat * scale[:, None], 支出)
    世帯.困窮[:] = 困窮

    支出 = np.maximum(np.rint(支出).astype(np.int64), 0)

    over = 支出.sum(axis=1) - cash
    支出[:, -1] -= np.maximum(over, 0)
    支出 = np.maximum(支出, 0)

    if 有効な法律:
        禁止を適用(有効な法律, 国, 支出, 設定)

    税率の並び = 消費税率(設定)
    消費税額 = 品目別消費税(支出, 税率の並び)
    net_to_firms = 支出 - 消費税額

    台帳.一括送金("家計", "企業", net_to_firms, "消費")
    台帳.一括送金("家計", "政府", 消費税額, "消費税")

    国.消費税負担 = 消費税額.sum(axis=1)

    世帯.貯蓄 -= 支出.sum(axis=1)

    国.数量 = net_to_firms.sum(axis=0) / 価格
    if 国.基準バスケット is None:
        国.基準バスケット = 国.数量.copy()

    sector_revenue = net_to_firms.sum(axis=0)
    企業 = 国.企業
    n_in_sector = np.bincount(企業.業種, minlength=len(品目一覧))
    取り分 = np.divide(sector_revenue, n_in_sector,
                      out=np.zeros(len(品目一覧)), where=n_in_sector > 0)
    企業.資本 += 取り分[企業.業種]

    return 支出
