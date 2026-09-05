from dataclasses import dataclass, field, fields

import numpy as np

from engine.params import 品目一覧


@dataclass
class 個人一覧:

    総数: int
    年齢: np.ndarray
    性別: np.ndarray
    世帯番号: np.ndarray
    就業状態: np.ndarray
    月給: np.ndarray
    基準労働時間: np.ndarray
    労働時間: np.ndarray
    勤務先: np.ndarray
    幸福度: np.ndarray
    生存: np.ndarray = None
    出生世帯: np.ndarray = None


@dataclass
class 世帯一覧:

    総数: int
    所得: np.ndarray
    世帯人員: np.ndarray
    子ども数: np.ndarray
    貯蓄: np.ndarray
    困窮: np.ndarray
    世帯主年齢: np.ndarray = None


@dataclass
class 企業一覧:
    総数: int
    業種: np.ndarray
    資本: np.ndarray


@dataclass
class 国家:
    個人: 個人一覧
    世帯: 世帯一覧
    企業: 企業一覧
    政府部門数: int
    サービス水準: float
    価格: np.ndarray
    経過月: int
    死亡数: int = 0
    出生数: int = 0
    相続件数: int = 0
    数量: np.ndarray = None
    基準バスケット: np.ndarray = None
    消費税負担: np.ndarray = None


def 国を用意する(人数: int, 世帯数: int, 企業数: int) -> 国家:

    個人 = 個人一覧(
        総数=人数,
        年齢=np.zeros(人数, dtype=np.uint8),
        性別=np.zeros(人数, dtype=np.uint8),
        世帯番号=np.full(人数, -1, dtype=np.int32),
        就業状態=np.zeros(人数, dtype=np.uint8),
        月給=np.zeros(人数, dtype=np.float64),
        基準労働時間=np.zeros(人数, dtype=np.float64),
        労働時間=np.zeros(人数, dtype=np.float64),
        勤務先=np.full(人数, -1, dtype=np.int32),
        幸福度=np.zeros(人数, dtype=np.float64),
        生存=np.ones(人数, dtype=bool),
        出生世帯=np.full(人数, -1, dtype=np.int32),
    )

    世帯 = 世帯一覧(
        総数=世帯数,
        所得=np.zeros(世帯数, dtype=np.int64),
        世帯人員=np.zeros(世帯数, dtype=np.uint8),
        子ども数=np.zeros(世帯数, dtype=np.uint8),
        貯蓄=np.zeros(世帯数, dtype=np.int64),
        困窮=np.zeros(世帯数, dtype=bool),
        世帯主年齢=np.zeros(世帯数, dtype=np.uint8),
    )

    企業 = 企業一覧(
        総数=企業数,
        業種=np.zeros(企業数, dtype=np.uint8),
        資本=np.zeros(企業数, dtype=np.float64),
    )

    return 国家(
        個人=個人,
        世帯=世帯,
        企業=企業,
        政府部門数=0,
        サービス水準=1.0,
        価格=np.ones(len(品目一覧), dtype=np.float64),
        経過月=0,
        数量=np.zeros(len(品目一覧), dtype=np.float64),
        基準バスケット=None,
        消費税負担=np.zeros(世帯数, dtype=np.int64),
    )


def 増やす(block, count: int) -> int:
    start = block.総数
    for field in fields(block):
        value = getattr(block, field.name)
        if isinstance(value, np.ndarray):
            filler = np.zeros(count, dtype=value.dtype)
            setattr(block, field.name, np.concatenate([value, filler]))
    block.総数 = start + count
    return start
