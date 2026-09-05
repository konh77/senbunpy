import numpy as np

口座一覧 = ("家計", "企業", "政府", "外部")


def 整数か(x):
    if isinstance(x, bool):
        return False
    return isinstance(x, (int, np.integer))


class 会計台帳:

    def __init__(self, opening=None):
        self.今月の増減 = {口座: 0 for 口座 in 口座一覧}
        self.残高 = {口座: 0 for 口座 in 口座一覧}
        self.名目別 = {}
        if opening:
            self.開始残高を置く(opening)

    def 開始残高を置く(self, opening: dict) -> None:
        for 口座, 額 in opening.items():
            if 口座 not in self.残高:
                raise ValueError(f"口座不明 {口座} / 正しくは {口座一覧}")
            if not 整数か(額):
                raise TypeError(f"整数円ではありません: {額!r} ({口座})")
            self.残高[口座] = int(額)

        合計 = sum(self.残高.values())
        if 合計 != 0:
            raise AssertionError(f"開始残高の総和が 0 ではありません: {合計} 円")

    def 送金(self, frm, to, 額, 名目):
        if not 整数か(額):
            raise TypeError(f"整数円ではありません: {額!r} ({frm}->{to} {名目})")
        if 額 < 0:
            raise ValueError(f"負の送金はできません: {額} ({名目})")
        if frm not in self.今月の増減:
            raise ValueError(f"口座不明 {frm} / 正しくは {口座一覧}")
        if to not in self.今月の増減:
            raise ValueError(f"口座不明 {to} / 正しくは {口座一覧}")

        額 = int(額)
        self.今月の増減[frm] -= 額
        self.今月の増減[to] += 額
        self.名目別[名目] = self.名目別.get(名目, 0) + 額

    def 一括送金(self, frm, to, amounts, 名目):
        if not isinstance(amounts, np.ndarray):
            raise TypeError(f"NumPyのアレイではありません: {type(amounts)} ({名目})")
        if amounts.dtype != np.int64:
            raise TypeError(f"int64ではありません： dtype={amounts.dtype} ({名目})")
        if (amounts < 0).any():
            raise ValueError(f"負の金額があります： ({frm}->{to} {名目})")

        self.送金(frm, to, int(amounts.sum()), 名目)

    def 保存則を検算(self):
        合計 = sum(self.今月の増減.values())
        if 合計 != 0:
            raise AssertionError(f"均衡が崩れました 総和={合計} 円 / delta={self.今月の増減}")

    def 月を締める(self):
        self.保存則を検算()
        for 口座 in self.今月の増減:
            self.残高[口座] += self.今月の増減[口座]
            self.今月の増減[口座] = 0
        self.名目別 = {}
