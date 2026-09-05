from dataclasses import dataclass
from enum import Enum, auto


class 字句種別(Enum):
    KEYWORD = auto()
    STRING = auto()
    NUMBER = auto()
    UNIT = auto()
    IDENT = auto()
    OP = auto()
    LBRACE = auto()
    RBRACE = auto()
    LPAREN = auto()
    RPAREN = auto()
    COLON = auto()
    COMMA = auto()
    SLASH = auto()
    EOF = auto()


@dataclass
class 字句:

    type: 字句種別
    値: object
    行: int
    桁: int

    def __repr__(self) -> str:
        return f"{self.type.name}({self.値!r})@{self.行}:{self.桁}"


予約語 = {
    "法律", "対象", "効果", "執行率", "財源", "施行",
    "where", "かつ", "または",
    "税率変更", "給付", "禁止",
    "基礎控除",
    "義務", "補助", "新税", "価格下限", "価格上限", "年齢制限", "労働規制",
    "国債", "後",
}

範囲外の概念 = {
    "外交", "条約", "憲法改正", "選挙", "移民", "国防",
    "金融政策", "為替", "関税", "輸出", "輸入", "教育制度",
}

予約語 |= 範囲外の概念

単位一覧 = ("ヶ月", "か月", "カ月", "万円", "円", "月", "年", "人", "歳", "日", "%", "％")
