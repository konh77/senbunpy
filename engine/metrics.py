import numpy as np

from engine.demography import 存続世帯
from engine.params import 就業, 失業
from engine.state import 国家


def ジニ係数(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=np.float64))
    総数 = len(x)
    合計 = x.sum()
    if 総数 == 0 or 合計 == 0:
        return 0.0
    i = np.arange(1, 総数 + 1)
    return float(2.0 * (i * x).sum() / (総数 * 合計) - (総数 + 1) / 総数)


def 物価指数(価格: np.ndarray, q0: np.ndarray, p0: np.ndarray) -> float:
    基準 = float((p0 * q0).sum())
    return 1.0 if 基準 == 0 else float((価格 * q0).sum() / 基準)


def 国内総生産(台帳, 国: 国家) -> int:
    c = 台帳.名目別.get("消費", 0)
    return int(c + 台帳.名目別.get("公共サービス", 0))


def 失業率(国: 国家) -> float:
    個人 = 国.個人
    就業者 = int((個人.就業状態 == 就業).sum())
    unemployed = int((個人.就業状態 == 失業).sum())
    return unemployed / (就業者 + unemployed) if 就業者 + unemployed else 0.0


def 資産ジニ(国: 国家) -> float:
    return ジニ係数(国.世帯.貯蓄[存続世帯(国.世帯)])


def 資産所得比(国: 国家) -> float:
    存続 = 存続世帯(国.世帯)
    所得 = int(国.世帯.所得[存続].sum()) * 12
    return float(国.世帯.貯蓄[存続].sum() / 所得) if 所得 else 0.0


def 高齢者資産シェア(国: 国家) -> float:
    存続 = 存続世帯(国.世帯)
    貯蓄 = 国.世帯.貯蓄
    合計 = int(貯蓄[存続].sum())
    if 合計 == 0:
        return 0.0
    return float(貯蓄[存続 & (国.世帯.世帯主年齢 >= 65)].sum() / 合計)


def 消費税の逆進性(国: 国家) -> float:
    存続 = 存続世帯(国.世帯)
    所得 = 国.世帯.所得[存続]
    消費税額 = 国.消費税負担[存続]
    if 消費税額 is None or len(所得) < 5:
        return 1.0

    並び順 = np.argsort(所得)
    fifth = max(len(所得) // 5, 1)
    下位, 上位 = 並び順[:fifth], 並び順[-fifth:]

    rate_bottom = 消費税額[下位].sum() / max(int(所得[下位].sum()), 1)
    rate_top = 消費税額[上位].sum() / max(int(所得[上位].sum()), 1)
    return float(rate_bottom / rate_top) if rate_top else 1.0


def 幸福度(国: 国家, 設定: dict) -> np.ndarray:
    世帯 = 国.世帯
    個人 = 国.個人

    等価人数 = np.sqrt(np.maximum(世帯.世帯人員, 1).astype(np.float64))
    基準額 = 設定["基準生活費"] * 等価人数

    暮らし向き = np.clip(世帯.所得 / (基準額 * 4.0), 0.0, 1.0)
    備え = np.clip(世帯.貯蓄 / (基準額 * 6.0), 0.0, 1.0)

    得点 = (0.55 * 暮らし向き + 0.25 * 備え)[個人.世帯番号]
    得点 = 得点 + 0.15 * min(国.サービス水準, 1.0)
    得点 = 得点 + 0.05 * (個人.就業状態 != 失業)
    return np.clip(得点, 0.0, 1.0)


def 支持率(国: 国家, 設定: dict) -> float:
    成人 = (国.個人.年齢 >= 18) & 国.個人.生存
    if not 成人.any():
        return 0.0
    return float((国.個人.幸福度[成人] >= 0.5).mean())


class 指標履歴:

    指標名 = (
        "GDP", "物価指数", "所得ジニ", "失業率", "政府債務", "財政収支",
        "幸福度", "支持率", "困窮世帯割合", "企業資本",
        "消費税の逆進性",
        "資産ジニ", "資産所得比", "高齢者資産シェア",
        "人口", "死亡数", "出生数", "相続税収", "利払い",
    )

    def __init__(self, 慣らし月数: int = 0):
        self.慣らし月数 = 慣らし月数
        self.月一覧: list[int] = []
        self.系列: dict[str, list] = {鍵: [] for 鍵 in self.指標名}

    def 記録する(self, month: int, 国: 国家, 台帳, 設定: dict) -> None:
        from engine.government import 財政収支, 政府債務

        国.個人.幸福度 = 幸福度(国, 設定)
        存続 = 存続世帯(国.世帯)

        self.月一覧.append(month)
        行データ = {
            "GDP": 国内総生産(台帳, 国),
            "物価指数": 物価指数(国.価格, 国.基準バスケット, np.ones_like(国.価格)),
            "所得ジニ": ジニ係数(国.世帯.所得[存続]),
            "失業率": 失業率(国),
            "政府債務": 政府債務(台帳),
            "財政収支": 財政収支(台帳),
            "幸福度": float(国.個人.幸福度[国.個人.生存].mean()),
            "支持率": 支持率(国, 設定),
            "困窮世帯割合": float(国.世帯.困窮[存続].mean()),
            "企業資本": int(国.企業.資本.sum()),
            "消費税の逆進性": 消費税の逆進性(国),
            "資産ジニ": 資産ジニ(国),
            "資産所得比": 資産所得比(国),
            "高齢者資産シェア": 高齢者資産シェア(国),
            "人口": int(国.個人.生存.sum()),
            "死亡数": int(国.死亡数),
            "出生数": int(国.出生数),
            "相続税収": int(台帳.名目別.get("相続税", 0)
                                   + 台帳.名目別.get("国庫帰属", 0)),
            "利払い": int(台帳.名目別.get("利子", 0)),
        }
        for 鍵 in self.指標名:
            self.系列[鍵].append(行データ[鍵])

    def 辞書にする(self) -> dict:
        integers = ("GDP", "政府債務", "財政収支", "企業資本",
                    "人口", "死亡数", "出生数", "相続税収", "利払い")
        系列 = {}
        for 鍵 in self.指標名:
            値の並び = self.系列[鍵]
            if 鍵 in integers:
                系列[鍵] = [int(v) for v in 値の並び]
            elif 鍵 == "資産所得比":
                系列[鍵] = [round(float(v), 4) for v in 値の並び]
            else:
                系列[鍵] = [round(float(v), 5) for v in 値の並び]
        return {"慣らし月数": self.慣らし月数, "月数": list(self.月一覧), "系列": 系列}
