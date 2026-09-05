import subprocess
import sys

import numpy as np
from numpy.random import default_rng

from engine.engine import 走らせる
from engine.init_pop import 人口を生成する, 初期データを読む
from engine.params import 既定設定

MONTHS = 6


def test_same_seed_same_population():
    a = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])
    b = 人口を生成する(初期データを読む(), default_rng(42), 既定設定["人口"])

    for field in ("年齢", "性別", "就業状態", "月給", "世帯番号", "勤務先"):
        np.testing.assert_array_equal(getattr(a.個人, field), getattr(b.個人, field))
    np.testing.assert_array_equal(a.世帯.所得, b.世帯.所得)


def test_same_seed_same_run():
    assert 走らせる(MONTHS, 乱数の種=42) == 走らせる(MONTHS, 乱数の種=42)


def test_different_seed_differs():
    assert 走らせる(MONTHS, 乱数の種=42) != 走らせる(MONTHS, 乱数の種=43)


def test_rng_is_created_in_exactly_one_place():
    hits = subprocess.run(
        [sys.executable, "-c",
         "import pathlib,re;"
         "print('\\n'.join(str(f) for f in pathlib.Path('engine').glob('*.py')"
         " if 'default_rng(' in f.read_text(encoding='utf-8')))"],
        capture_output=True, text=True, check=True,
    ).stdout.split()

    allowed = {"engine/engine.py", "engine/init_pop.py"}
    assert set(hits) <= allowed, f"想定外の場所で乱数を作っている: {set(hits) - allowed}"
