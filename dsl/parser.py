from dsl.ast_nodes import (
    比較, 条件, 効果一覧, 執行率, 財源, 法律,
    禁止, 税率変更, 対象, 施行, 給付, 範囲外, 数量,
)
from dsl.errors import 構文エラー
from dsl.lexer import 字句に分ける
from dsl.tokens import 範囲外の概念, 字句, 字句種別

対象種別一覧 = ("人", "世帯", "企業")

実装済みの効果 = ("税率変更", "給付", "禁止")
範囲外の効果 = ("義務", "補助", "新税", "価格下限", "価格上限", "年齢制限", "労働規制")


class 構文解析器:
    def __init__(self, 字句列: list[字句], 原文: str = ""):
        self.字句列 = 字句列
        self.原文 = 原文
        self.i = 0


    def 先を見る(self, ahead: int = 0) -> 字句:
        i = min(self.i + ahead, len(self.字句列) - 1)
        return self.字句列[i]

    def 次へ進む(self) -> 字句:
        字句 = self.先を見る()
        if 字句.type != 字句種別.EOF:
            self.i += 1
        return 字句

    def 型が一致するか(self, type_: 字句種別, value=None) -> bool:
        字句 = self.先を見る()
        if 字句.type != type_:
            return False
        return value is None or 字句.値 == value

    def 一致すれば進む(self, type_: 字句種別, value=None) -> 字句 | None:
        if self.型が一致するか(type_, value):
            return self.次へ進む()
        return None

    def 無ければ叱る(self, type_: 字句種別, 本文: str, 助言: str = "") -> 字句:
        if self.型が一致するか(type_):
            return self.次へ進む()
        self.叱る(本文, 助言)

    def 叱る(self, 本文: str, 助言: str = "") -> None:
        字句 = self.先を見る()
        if 字句.type == 字句種別.EOF:
            本文 = f"{本文}(文の終わりに来てしまいました)"
        raise 構文エラー(本文, 字句.行, 字句.桁, 助言=助言, 原文=self.原文)


    def 解析する(self) -> 法律:
        start = self.先を見る()
        self.予約語を求める("法律", "法律は 法律 \"名前\" { … } の形で書きます")

        name_token = self.無ければ叱る(
            字句種別.STRING, "法律の名前が必要です",
            助言='法律 "こども未来給付法" { … } のように " で囲んで書きます',
        )
        self.無ければ叱る(字句種別.LBRACE, "法律名の後には '{' が必要です")

        節 = []
        while not self.型が一致するか(字句種別.RBRACE):
            if self.型が一致するか(字句種別.EOF):
                raise 構文エラー(
                    "'}' が閉じられていません", start.行, start.桁,
                    助言="法律の本体は { で開いて } で閉じます", 原文=self.原文,
                )
            変更前 = self.i
            節.append(self.節を解析())
            if self.i == 変更前:
                self.叱る("ここが読めませんでした")

        self.次へ進む()

        if not 節:
            raise 構文エラー(
                "法律の中身が空です", start.行, start.桁,
                助言="少なくとも 効果 { … } が1つ必要です", 原文=self.原文,
            )
        return 法律(name_token.値, 節, start.行, start.桁, self.原文)

    def 予約語を求める(self, 語: str, 助言: str = "") -> 字句:
        if self.型が一致するか(字句種別.KEYWORD, 語):
            return self.次へ進む()
        self.叱る(f"'{語}' が必要です", 助言)


    def 節を解析(self):
        字句 = self.先を見る()

        if 字句.type != 字句種別.KEYWORD:
            self.叱る(
                f"'{字句.値}' は法律の節として読めません",
                助言="節に書けるのは 対象 / 効果 / 財源 / 執行率 / 施行 です",
            )

        table = {
            "対象": self.対象を解析,
            "効果": self.効果を解析,
            "財源": self.財源を解析,
            "執行率": self.執行率を解析,
            "施行": self.施行を解析,
        }
        if 字句.値 in table:
            return table[字句.値]()

        if 字句.値 in 範囲外の概念:
            self.次へ進む()
            self.次の節まで飛ばす()
            return 範囲外(字句.値, 字句.行, 字句.桁)

        self.叱る(
            f"'{字句.値}' は法律の節として読めません",
            助言="節に書けるのは 対象 / 効果 / 財源 / 執行率 / 施行 です",
        )


    def 対象を解析(self) -> 対象:
        start = self.次へ進む()
        self.無ければ叱る(字句種別.COLON, "'対象' の後には ':' が必要です",
                    助言="対象: 世帯 where 子ども数 >= 1 のように書きます")

        entity_token = self.先を見る()
        if entity_token.type not in (字句種別.IDENT, 字句種別.KEYWORD):
            self.叱る("対象が必要です", 助言=f"書けるのは {' / '.join(対象種別一覧)} です")
        対象種別 = self.次へ進む().値

        if 対象種別 not in 対象種別一覧:
            self.位置を指して叱る(
                entity_token, f"'{対象種別}' は対象にできません",
                助言=f"この模型に存在するのは {' / '.join(対象種別一覧)} の3つだけです",
            )

        条件 = None
        if self.一致すれば進む(字句種別.KEYWORD, "where"):
            条件 = self.条件を解析()

        return 対象(対象種別, 条件, start.行, start.桁)

    def 位置を指して叱る(self, 字句: 字句, 本文: str, 助言: str = "") -> None:
        raise 構文エラー(本文, 字句.行, 字句.桁, 助言=助言, 原文=self.原文)


    def 条件を解析(self) -> 条件:
        比較の並び = [self.比較を解析()]
        接続語 = []
        while self.型が一致するか(字句種別.KEYWORD, "かつ") or self.型が一致するか(字句種別.KEYWORD, "または"):
            接続語.append(self.次へ進む().値)
            比較の並び.append(self.比較を解析())
        return 条件(比較の並び, 接続語)

    def 比較を解析(self) -> 比較:
        attr_token = self.先を見る()
        if attr_token.type != 字句種別.IDENT:
            self.叱る("条件は 属性 比較 値 の形で書きます",
                      助言="例: 年齢 < 18 / 子ども数 >= 1")
        属性 = self.次へ進む().値

        if not self.型が一致するか(字句種別.OP):
            self.叱る(f"'{属性}' の後には比較記号が必要です",
                      助言="使えるのは < > <= >= == != です")
        演算子 = self.次へ進む().値
        if 演算子 not in ("<", ">", "<=", ">=", "==", "!=", "="):
            self.位置を指して叱る(attr_token, f"'{演算子}' は条件に使えません",
                         助言="使えるのは < > <= >= == != です")

        return 比較(属性, "==" if 演算子 == "=" else 演算子,
                          self.数量を解析(), attr_token.行, attr_token.桁)

    def 数量を解析(self) -> 数量:
        字句 = self.先を見る()
        if 字句.type != 字句種別.NUMBER:
            self.叱る(
                "数値が必要です",
                助言='文字列ではなく数で書きます。「高い」ではなく 80% のように',
            )
        数 = self.次へ進む().値
        単位 = self.次へ進む().値 if self.型が一致するか(字句種別.UNIT) else None
        return 数量(数, 単位, 字句.行, 字句.桁)


    def 効果を解析(self) -> 効果一覧:
        start = self.次へ進む()
        self.無ければ叱る(字句種別.LBRACE, "'効果' の後には '{' が必要です",
                    助言="効果は複数書けるので、必ず波括弧でまとめます")

        効果 = []
        while not self.型が一致するか(字句種別.RBRACE):
            if self.型が一致するか(字句種別.EOF):
                raise 構文エラー("効果の '}' が閉じられていません",
                                 start.行, start.桁, 原文=self.原文)
            変更前 = self.i
            効果.append(self.効果ひとつを解析())
            if self.i == 変更前:
                self.叱る("ここが読めませんでした")
        self.次へ進む()

        if not 効果:
            raise 構文エラー(
                "効果が空です", start.行, start.桁,
                助言="効果 { 給付: 15000円/月 } のように、1つ以上書きます", 原文=self.原文,
            )
        return 効果一覧(効果, start.行, start.桁)

    def 効果ひとつを解析(self):
        字句 = self.先を見る()
        if 字句.type != 字句種別.KEYWORD:
            self.叱る(f"'{字句.値}' は効果として読めません",
                      助言=f"書けるのは {' / '.join(実装済みの効果)} です")

        if 字句.値 in 範囲外の効果 or 字句.値 in 範囲外の概念:
            self.次へ進む()
            self.次の効果まで飛ばす()
            return 範囲外(字句.値, 字句.行, 字句.桁)

        table = {
            "税率変更": self.税率変更を解析,
            "給付": self.給付を解析,
            "禁止": self.禁止を解析,
        }
        if 字句.値 in table:
            return table[字句.値]()

        self.叱る(f"'{字句.値}' は効果として読めません",
                  助言=f"書けるのは {' / '.join(実装済みの効果)} です")

    def 次の節まで飛ばす(self) -> None:
        self.次の効果まで飛ばす()

    def 次の効果まで飛ばす(self) -> None:
        depth = 0
        while not self.型が一致するか(字句種別.EOF):
            if self.型が一致するか(字句種別.LBRACE):
                depth += 1
            elif self.型が一致するか(字句種別.RBRACE):
                if depth == 0:
                    return
                depth -= 1
            elif depth == 0 and self.先を見る().type == 字句種別.KEYWORD:
                return
            self.次へ進む()


    def 税率変更を解析(self) -> 税率変更:
        start = self.次へ進む()
        self.無ければ叱る(字句種別.COLON, "'税率変更' の後には ':' が必要です",
                    助言="税率変更: 消費税(食料品) 8% → 0% のように書きます")

        tax_token = self.無ければ叱る(字句種別.IDENT, "変更する税の名前が必要です",
                                助言="例: 消費税 / 所得税")
        品目 = None
        if self.一致すれば進む(字句種別.LPAREN):
            if self.先を見る().type not in (字句種別.IDENT, 字句種別.KEYWORD):
                self.叱る("括弧の中には対象品目を書きます", 助言="例: 消費税(食料品)")
            品目 = self.次へ進む().値
            self.無ければ叱る(字句種別.RPAREN, "')' が閉じられていません")

        変更前 = self.数量を解析()
        if not self.一致すれば進む(字句種別.OP, "->"):
            self.叱る("変更前と変更後は '→' でつなぎます",
                      助言="8% → 0% のように書きます(-> でも構いません)")
        変更後 = self.数量を解析()

        return 税率変更(tax_token.値, 品目, 変更前, 変更後, start.行, start.桁)

    def 給付を解析(self) -> 給付:
        start = self.次へ進む()
        self.無ければ叱る(字句種別.COLON, "'給付' の後には ':' が必要です",
                    助言="給付: 15000円/月 × 子ども数 のように書きます")

        額 = self.数量を解析()
        期間 = None
        if self.一致すれば進む(字句種別.SLASH):
            単位 = self.無ければ叱る(字句種別.UNIT, "'/' の後には期間が必要です",
                               助言="円/月 または 円/年 と書きます")
            期間 = 単位.値

        掛ける対象 = None
        if self.一致すれば進む(字句種別.OP, "×"):
            per_token = self.先を見る()
            if per_token.type != 字句種別.IDENT:
                self.叱る("'×' の後には掛ける対象が必要です",
                          助言="例: × 子ども数")
            掛ける対象 = self.次へ進む().値

        return 給付(額, 期間, 掛ける対象, start.行, start.桁)

    def 禁止を解析(self) -> 禁止:
        start = self.次へ進む()
        self.無ければ叱る(字句種別.COLON, "'禁止' の後には ':' が必要です",
                    助言="禁止: 支出(カテゴリ=ガチャ) > 5000円/月 のように書きます")

        what_token = self.無ければ叱る(字句種別.IDENT, "禁止する対象が必要です",
                                 助言="例: 支出(カテゴリ=ガチャ)")
        引数 = self.引数を解析() if self.一致すれば進む(字句種別.LPAREN) else {}

        演算子, 上限, 期間 = ">", None, None
        if self.型が一致するか(字句種別.OP):
            演算子 = self.次へ進む().値
            上限 = self.数量を解析()
            if self.一致すれば進む(字句種別.SLASH):
                期間 = self.無ければ叱る(字句種別.UNIT, "'/' の後には期間が必要です").値

        return 禁止(what_token.値, 引数, 演算子, 上限, 期間,
                        start.行, start.桁)

    def 引数を解析(self) -> dict:
        引数 = {}
        while not self.型が一致するか(字句種別.RPAREN):
            if self.型が一致するか(字句種別.EOF):
                self.叱る("')' が閉じられていません")

            key_token = self.先を見る()
            if key_token.type not in (字句種別.IDENT, 字句種別.KEYWORD):
                self.叱る("括弧の中は 名前=値 の形で書きます")
            鍵 = self.次へ進む().値

            if not self.一致すれば進む(字句種別.OP, "="):
                self.叱る(f"'{鍵}' の後には '=' が必要です",
                          助言="括弧の中は カテゴリ=ガチャ のように書きます")

            parts = []
            while not self.型が一致するか(字句種別.COMMA) and not self.型が一致するか(字句種別.RPAREN):
                if self.型が一致するか(字句種別.EOF):
                    self.叱る("')' が閉じられていません")
                parts.append(str(self.次へ進む().値))
            引数[鍵] = "".join(parts)

            if not self.一致すれば進む(字句種別.COMMA):
                break

        self.無ければ叱る(字句種別.RPAREN, "')' が閉じられていません")
        return 引数


    def 財源を解析(self) -> 財源:
        start = self.次へ進む()
        self.無ければ叱る(字句種別.COLON, "'財源' の後には ':' が必要です",
                    助言="財源: 所得税(+1%) または 財源: 国債 と書きます")

        if self.一致すれば進む(字句種別.KEYWORD, "国債"):
            return 財源("bond", None, None, start.行, start.桁)

        tax_token = self.無ければ叱る(字句種別.IDENT, "財源となる税の名前が必要です",
                                助言="例: 所得税(+1%) / 消費税(+2%) / 国債")
        今月の増減 = None
        if self.一致すれば進む(字句種別.LPAREN):
            sign = 1
            if self.一致すれば進む(字句種別.OP, "-"):
                sign = -1
            else:
                self.一致すれば進む(字句種別.OP, "+")
            今月の増減 = self.数量を解析()
            今月の増減.数 *= sign
            self.無ければ叱る(字句種別.RPAREN, "')' が閉じられていません")

        return 財源("税", tax_token.値, 今月の増減, start.行, start.桁)

    def 執行率を解析(self) -> 執行率:
        start = self.次へ進む()
        self.無ければ叱る(字句種別.COLON, "'執行率' の後には ':' が必要です",
                    助言="執行率: 80% のように書きます")
        return 執行率(self.数量を解析(), start.行, start.桁)

    def 施行を解析(self) -> 施行:
        start = self.次へ進む()
        self.無ければ叱る(字句種別.COLON, "'施行' の後には ':' が必要です",
                    助言="施行: 6ヶ月後 または 施行: 即日 と書きます")

        if self.型が一致するか(字句種別.IDENT):
            語 = self.次へ進む().値
            if 語 not in ("即日", "即時"):
                self.叱る(f"'{語}' は施行時期として読めません",
                          助言="施行: 6ヶ月後 または 施行: 即日 と書きます")
            return 施行(0, start.行, start.桁)

        value = self.数量を解析()
        self.一致すれば進む(字句種別.KEYWORD, "後")

        months = int(value.数)
        if value.単位 == "年":
            months *= 12
        elif value.単位 not in ("ヶ月", "か月", "カ月", "月", None):
            self.叱る(f"施行時期の単位に '{value.単位}' は使えません",
                      助言="ヶ月 か 年 で書きます")
        return 施行(months, start.行, start.桁)


def 解析する(原文: str) -> 法律:
    return 構文解析器(字句に分ける(原文), 原文).解析する()
