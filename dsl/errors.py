class 法律エラー(Exception):

    def __init__(self, 本文: str, 行: int = 0, 桁: int = 0,
                 助言: str = "", 原文: str = ""):
        super().__init__(本文)
        self.本文 = 本文
        self.行 = 行
        self.桁 = 桁
        self.助言 = 助言
        self.原文 = 原文

    def 該当行(self) -> str:
        if not self.原文 or self.行 <= 0:
            return ""
        行の並び = self.原文.splitlines()
        if self.行 > len(行の並び):
            return ""
        text = 行の並び[self.行 - 1]
        pad = "".join("　" if ord(c) > 0x2000 else " " for c in text[: self.桁 - 1])
        return f"  {text}\n  {pad}^"

    def __str__(self) -> str:
        head = f"{self.行}行目 {self.桁}文字目: {self.本文}" if self.行 else self.本文
        parts = [head]
        caret = self.該当行()
        if caret:
            parts.append(caret)
        if self.助言:
            parts.append(f"  ヒント: {self.助言}")
        return "\n".join(parts)


class 字句エラー(法律エラー):
    pass


class 構文エラー(法律エラー):
    pass


class 検証エラー(法律エラー):
    pass


class 範囲外エラー(検証エラー):
    pass


class 警告(法律エラー):
    pass
