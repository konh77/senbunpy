import numpy as np

標本数 = 100


class 街の記録:
    """3D表示のための観測。**台帳には一切触らない。読むだけ。**

    集計値だけ渡すと、画面の人の動きは「それっぽく作った嘘」になる。
    実際に動いている世帯を標本抽出して、その月の所得・貯蓄・出来事をそのまま渡す。
    """

    def __init__(self, 国, 乱数):
        世帯数 = 国.世帯.総数
        n = min(標本数, 世帯数)
        self.標本 = np.sort(乱数.choice(世帯数, size=n, replace=False))
        self.属性 = []
        self.月ごと = []
        self.前の存続 = np.ones(n, dtype=bool)

    def 属性を固める(self, 国):
        世帯 = 国.世帯
        for 番号 in self.標本:
            self.属性.append({
                "世帯人員": int(世帯.世帯人員[番号]),
                "子ども数": int(世帯.子ども数[番号]),
                "世帯主年齢": int(世帯.世帯主年齢[番号]),
            })

    def 記録する(self, 国, 台帳):
        世帯 = 国.世帯
        所得 = 世帯.所得[self.標本]
        貯蓄 = 世帯.貯蓄[self.標本]
        困窮 = 世帯.困窮[self.標本]
        存続 = 世帯.世帯人員[self.標本] > 0

        出来事 = []
        消えた = self.前の存続 & ~存続
        for i in np.flatnonzero(消えた):
            出来事.append({"種類": "世帯消滅", "標本": int(i)})
        self.前の存続 = 存続.copy()

        self.月ごと.append({
            "資金の流れ": {名目: int(額) for 名目, 額 in 台帳.名目別.items()},
            "口座": {口座: int(台帳.残高[口座] + 台帳.今月の増減[口座])
                     for 口座 in ("家計", "企業", "政府")},
            "世帯": [[int(所得[i]), int(貯蓄[i]), bool(困窮[i]), bool(存続[i])]
                     for i in range(len(self.標本))],
            "出来事": 出来事,
            "死亡": int(国.死亡数),
            "出生": int(国.出生数),
            "相続": int(国.相続件数),
            "世帯主年齢": [int(世帯.世帯主年齢[番号]) for 番号 in self.標本],
        })

    def 辞書にする(self) -> dict:
        return {"属性": self.属性, "月ごと": self.月ごと}
