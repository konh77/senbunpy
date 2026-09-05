from dsl.errors import 字句エラー
from dsl.tokens import 予約語, 単位一覧, 字句, 字句種別

全角から半角 = {
    "　": " ", "（": "(", "）": ")", "｛": "{", "｝": "}",
    "：": ":", "，": ",", "、": ",", "＝": "=", "＜": "<", "＞": ">",
    "＋": "+", "－": "-", "／": "/", "％": "%", "＊": "*",
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
}

区切り記号 = {
    "{": 字句種別.LBRACE, "}": 字句種別.RBRACE,
    "(": 字句種別.LPAREN, ")": 字句種別.RPAREN,
    ":": 字句種別.COLON, ",": 字句種別.COMMA,
    "/": 字句種別.SLASH,
}

二文字演算子 = (">=", "<=", "==", "!=", "->")
一文字演算子 = ("<", ">", "=", "+", "-", "×", "*", "→")


class 字句解析器:
    def __init__(self, 原文: str):
        self.原文 = 原文
        self.位置 = 0
        self.行 = 1
        self.桁 = 1
        self.字句列: list[字句] = []


    def 終端か(self) -> bool:
        return self.位置 >= len(self.原文)

    def 先を見る(self, ahead: int = 0) -> str:
        i = self.位置 + ahead
        return self.原文[i] if i < len(self.原文) else ""

    def 半角に読み替える(self, ahead: int = 0) -> str:
        c = self.先を見る(ahead)
        return 全角から半角.get(c, c)

    def 次へ進む(self, 文字数: int = 1) -> str:
        out = self.原文[self.位置 : self.位置 + 文字数]
        for c in out:
            if c == "\n":
                self.行 += 1
                self.桁 = 1
            else:
                self.桁 += 1
        self.位置 += 文字数
        return out

    def 字句を足す(self, type_: 字句種別, value, 行: int, 桁: int) -> None:
        self.字句列.append(字句(type_, value, 行, 桁))


    def 字句に分ける(self) -> list[字句]:
        while not self.終端か():
            if self.空白と注釈を飛ばす():
                continue

            行, 桁 = self.行, self.桁
            c = self.半角に読み替える()

            if c == '"':
                self.文字列を読む(行, 桁)
            elif c.isdigit():
                self.数値を読む(行, 桁)
            elif self.演算子を読む(行, 桁):
                pass
            elif c in 区切り記号:
                self.次へ進む()
                self.字句を足す(区切り記号[c], c, 行, 桁)
            elif c in ("%",):
                self.次へ進む()
                self.字句を足す(字句種別.UNIT, "%", 行, 桁)
            elif self.語を作る文字か(self.先を見る()):
                self.語を読む(行, 桁)
            else:
                raise 字句エラー(
                    f"'{self.先を見る()}' は法律文に使えない文字です",
                    行, 桁, 原文=self.原文,
                    助言="使えるのは 日本語・英数字・記号 {} ( ) : , / < > = + → × と "
                         "コメント(// または #)です",
                )

        self.字句を足す(字句種別.EOF, None, self.行, self.桁)
        return self.字句列

    def 空白と注釈を飛ばす(self) -> bool:
        c = self.先を見る()
        if c in (" ", "\t", "\r", "\n", "　"):
            self.次へ進む()
            return True
        if c == "#" or (c == "/" and self.先を見る(1) == "/"):
            while not self.終端か() and self.先を見る() != "\n":
                self.次へ進む()
            return True
        return False

    def 文字列を読む(self, 行: int, 桁: int) -> None:
        self.次へ進む()
        chars = []
        while not self.終端か() and self.半角に読み替える() != '"':
            if self.先を見る() == "\n":
                raise 字句エラー(
                    "文字列が閉じられていません", 行, 桁, 原文=self.原文,
                    助言='法律名は "こども未来給付法" のように " で囲みます',
                )
            chars.append(self.次へ進む())
        if self.終端か():
            raise 字句エラー('" が閉じられていません', 行, 桁, 原文=self.原文)
        self.次へ進む()
        self.字句を足す(字句種別.STRING, "".join(chars), 行, 桁)

    def 数値を読む(self, 行: int, 桁: int) -> None:
        chars = []
        while not self.終端か() and (self.半角に読み替える().isdigit() or self.半角に読み替える() == "."):
            chars.append(全角から半角.get(self.次へ進む(), self.原文[self.位置 - 1]))
        text = "".join(chars)
        value = float(text) if "." in text else int(text)
        self.字句を足す(字句種別.NUMBER, value, 行, 桁)

    def 演算子を読む(self, 行: int, 桁: int) -> bool:
        two = self.半角に読み替える() + self.半角に読み替える(1)
        if two in 二文字演算子:
            self.次へ進む(2)
            self.字句を足す(字句種別.OP, "->" if two == "->" else two, 行, 桁)
            return True
        one = self.半角に読み替える()
        if one in 一文字演算子:
            self.次へ進む()
            self.字句を足す(字句種別.OP, {"→": "->", "*": "×"}.get(one, one), 行, 桁)
            return True
        return False

    @staticmethod
    def 語を作る文字か(c: str) -> bool:
        return bool(c) and (c.isalnum() or c in "ーｰ_")

    def 語を読む(self, 行: int, 桁: int) -> None:
        chars = []
        while self.語を作る文字か(self.先を見る()):
            chars.append(self.次へ進む())
        語 = "".join(chars)

        if 語 in 予約語:
            self.字句を足す(字句種別.KEYWORD, 語, 行, 桁)
            return

        prev = self.字句列[-1] if self.字句列 else None
        after_number = prev is not None and prev.type == 字句種別.NUMBER
        after_slash = prev is not None and prev.type == 字句種別.SLASH

        if 語 in 単位一覧 and (after_number or after_slash):
            self.字句を足す(字句種別.UNIT, 語, 行, 桁)
            return

        if after_number:
            for 単位 in 単位一覧:
                if 語.startswith(単位):
                    self.字句を足す(字句種別.UNIT, 単位, 行, 桁)
                    rest = 語[len(単位):]
                    if rest:
                        rest_col = 桁 + len(単位)
                        type_ = 字句種別.KEYWORD if rest in 予約語 else 字句種別.IDENT
                        self.字句を足す(type_, rest, 行, rest_col)
                    return

        self.字句を足す(字句種別.IDENT, 語, 行, 桁)


def 字句に分ける(原文: str) -> list[字句]:
    return 字句解析器(原文).字句に分ける()
