"""棋子常量、中文名称、归属与子力价值。

棋盘字符约定（与 TCHESS 一致）：
    红方（大写）：K 帅  A 仕  B 相  N 马  R 车  C 炮  P 兵
    黑方（小写）：k 将  a 士  b 象  n 马  r 车  c 炮  p 卒
"""

# 红方棋子
RED_KING = "K"
RED_ADVISOR = "A"
RED_ELEPHANT = "B"
RED_HORSE = "N"
RED_CHARIOT = "R"
RED_CANNON = "C"
RED_PAWN = "P"

# 黑方棋子
BLACK_KING = "k"
BLACK_ADVISOR = "a"
BLACK_ELEPHANT = "b"
BLACK_HORSE = "n"
BLACK_CHARIOT = "r"
BLACK_CANNON = "c"
BLACK_PAWN = "p"

EMPTY = " "

# 棋子中文名
PIECE_NAME = {
    "K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵",
    "k": "将", "a": "士", "b": "象", "n": "马", "r": "车", "c": "炮", "p": "卒",
}

# 基础子力价值（兵卒为未过河价值；过河后见 material_value）
PIECE_VALUE = {
    "K": 10000, "k": 10000,
    "R": 900, "r": 900,
    "C": 450, "c": 450,
    "N": 400, "n": 400,
    "A": 200, "a": 200,
    "B": 200, "b": 200,
    "P": 100, "p": 100,
}

# 过河兵卒的价值
PAWN_CROSSED_VALUE = 200


def is_red(piece: str) -> bool:
    """是否为红方棋子（大写）。"""
    return piece != EMPTY and piece.isupper()


def piece_name(piece: str) -> str:
    """棋子中文名。"""
    return PIECE_NAME.get(piece, "?")


def piece_kind(piece: str) -> str:
    """棋子种类（统一小写）：k/a/b/n/r/c/p。"""
    return piece.lower()


def is_pawn(piece: str) -> bool:
    return piece in ("P", "p")


def has_crossed_river(piece: str, y: int) -> bool:
    """兵/卒是否已过河。

    红兵（P）从红方半场（y>=5）向 y 减小方向走，y<5 即过河；
    黑卒（p）从黑方半场（y<=4）向 y 增大方向走，y>=5 即过河。
    """
    if piece == "P":
        return y < 5
    if piece == "p":
        return y >= 5
    return False


def material_value(piece: str, y: int = -1) -> int:
    """子力价值；兵卒过河后价值升高。"""
    if is_pawn(piece) and y >= 0 and has_crossed_river(piece, y):
        return PAWN_CROSSED_VALUE
    return PIECE_VALUE.get(piece, 0)
