"""棋盘表示、着法字符串解析、应用走法与 FEN 解析。

坐标约定：
    board[y][x]，y 为行（0=黑方底线 … 9=红方底线），x 为列（0…8）。
    着法字符串形如 "b0c2"：列字母(a-i) + 行数字(0-9)，前两位为起点、后两位为终点。
    着法字符串遵循 UCI 编号：rank 从红方底线起算，与棋盘视觉行方向相反，
    故 y = 9 - rank、rank = 9 - y（file 与 x 同向）。
"""
from typing import List, Optional, Tuple

from .pieces import EMPTY, is_red

ROWS = 10
COLS = 9

# 一个交叉点坐标
Point = Tuple[int, int]
# 一步着法：(起点 y,x, 终点 y,x)
MoveCoords = Tuple[int, int, int, int]


def new_board() -> List[List[str]]:
    """空棋盘。"""
    return [[EMPTY] * COLS for _ in range(ROWS)]


def in_bounds(y: int, x: int) -> bool:
    return 0 <= y < ROWS and 0 <= x < COLS


def clone_board(board: List[List[str]]) -> List[List[str]]:
    """深拷贝棋盘。"""
    return [row[:] for row in board]


def coords_to_move(fy: int, fx: int, ty: int, tx: int) -> str:
    """坐标 -> 着法字符串，如 (9,1,7,2) -> 'b0c2'。

    UCI rank 从红方底线起算：rank = 9 - y。
    """
    return f"{chr(ord('a') + fx)}{9 - fy}{chr(ord('a') + tx)}{9 - ty}"


def parse_move(move: str) -> MoveCoords:
    """着法字符串 -> (fy, fx, ty, tx)。

    UCI rank 从红方底线起算，棋盘视觉行 y = 9 - rank。
    """
    if not move or len(move) < 4:
        raise ValueError(f"非法着法: {move!r}")
    fx = ord(move[0]) - ord("a")
    fy = 9 - int(move[1])
    tx = ord(move[2]) - ord("a")
    ty = 9 - int(move[3])
    if not (0 <= fx < COLS and 0 <= tx < COLS and 0 <= fy < ROWS and 0 <= ty < ROWS):
        raise ValueError(f"着法越界: {move!r}")
    return fy, fx, ty, tx


def apply_move(board: List[List[str]], move: str) -> List[List[str]]:
    """应用着法，返回新棋盘（不修改原棋盘）。"""
    fy, fx, ty, tx = parse_move(move)
    nb = clone_board(board)
    nb[ty][tx] = nb[fy][fx]
    nb[fy][fx] = EMPTY
    return nb


def find_king(board: List[List[str]], red: bool) -> Optional[Point]:
    """找到指定方将/帅的位置 (y,x)。"""
    target = "K" if red else "k"
    for y in range(ROWS):
        for x in range(COLS):
            if board[y][x] == target:
                return y, x
    return None


def list_pieces(board: List[List[str]], red: Optional[bool] = None) -> List[Tuple[int, int, str]]:
    """列出棋子 (y,x,piece)；red=None 时列全部。"""
    result = []
    for y in range(ROWS):
        for x in range(COLS):
            p = board[y][x]
            if p == EMPTY:
                continue
            if red is None or is_red(p) == red:
                result.append((y, x, p))
    return result


def fen_to_board(fen: str) -> List[List[str]]:
    """标准方向 FEN（红方在下）-> 棋盘。

    仅用于测试样例。TCHESS 实际下发的 board 字段已是标准方向，无需转换。
    """
    board = new_board()
    rows = fen.split(" ")[0].split("/")
    if len(rows) != ROWS:
        raise ValueError(f"FEN 行数不为 {ROWS}: {fen!r}")
    for y, row in enumerate(rows):
        x = 0
        for ch in row:
            if ch.isdigit():
                x += int(ch)
            else:
                board[y][x] = ch
                x += 1
    return board


def initial_board() -> List[List[str]]:
    """开局初始棋盘。"""
    return fen_to_board(
        "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR"
    )
