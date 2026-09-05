from dataclasses import dataclass, field
from typing import Any


@dataclass
class 数量:

    数: float
    単位: str | None = None
    行: int = 0
    桁: int = 0

    def 割合にする(self) -> float:
        return self.数 / 100.0 if self.単位 == "%" else float(self.数)

    def 円にする(self) -> int:
        return int(round(self.数 * (10_000 if self.単位 == "万円" else 1)))


@dataclass
class 比較:
    属性: str
    演算子: str
    値: 数量
    行: int = 0
    桁: int = 0


@dataclass
class 条件:

    比較の並び: list[比較] = field(default_factory=list)
    接続語: list[str] = field(default_factory=list)


@dataclass
class 対象:
    対象種別: str
    条件: 条件 | None = None
    行: int = 0
    桁: int = 0


@dataclass
class 税率変更:

    税: str
    品目: str | None
    変更前: 数量
    変更後: 数量
    行: int = 0
    桁: int = 0


@dataclass
class 給付:

    額: 数量
    期間: str | None = None
    掛ける対象: str | None = None
    行: int = 0
    桁: int = 0


@dataclass
class 禁止:

    対象: str
    引数: dict = field(default_factory=dict)
    演算子: str = ">"
    上限: 数量 | None = None
    期間: str | None = None
    行: int = 0
    桁: int = 0


@dataclass
class 範囲外:

    語: str
    行: int = 0
    桁: int = 0


@dataclass
class 効果一覧:
    効果: list = field(default_factory=list)
    行: int = 0
    桁: int = 0


@dataclass
class 財源:
    種類: str
    税: str | None = None
    今月の増減: 数量 | None = None
    行: int = 0
    桁: int = 0


@dataclass
class 執行率:
    割合: 数量
    行: int = 0
    桁: int = 0


@dataclass
class 施行:

    施行月数: int = 0
    行: int = 0
    桁: int = 0


@dataclass
class 法律:
    name: str
    節: list = field(default_factory=list)
    行: int = 0
    桁: int = 0
    原文: str = ""

    def 節を探す(self, node_type) -> Any:
        for clause in self.節:
            if isinstance(clause, node_type):
                return clause
        return None

    def 効果(self) -> list:
        node = self.節を探す(効果一覧)
        return node.効果 if node else []
