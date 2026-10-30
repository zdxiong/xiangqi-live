"""中国象棋走法规则、攻击关系判断。

规则严格对应 Java 端 XiangqiUtils.canGo / isJiang：
    can_move 为“伪合法”（不考虑送将、将帅照面）；
    legal_moves 在其基础上过滤走完后己方仍被将军的走法。
战术意图分析见 app/engine/intents.py。
"""
from typing import List, Optional, Tuple

from .board import (
    ROWS, COLS, Point, apply_move, coords_to_move,
    find_king, list_pieces,
)
from .pieces import EMPTY, is_red


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def can_move(board: List[List[str]], fy: int, fx: int, ty: int, tx: int) -> bool:
    """棋子 (fy,fx) 能否走到 (ty,tx)（伪合法，不含送将/照面判断）。"""
    piece = board[fy][fx]
    if piece == EMPTY:
        return False
    target = board[ty][tx]
    if target != EMPTY and is_red(target) == is_red(piece):
        # 落点为己方棋子
        return False

    kind = piece.lower()
    dy = ty - fy
    dx = tx - fx

    if kind == "r":
        # 车：直线，路径无子
        if fy != ty and fx != tx:
            return False
        if fy == ty:
            lo, hi = sorted((fx, tx))
            return all(board[fy][x] == EMPTY for x in range(lo + 1, hi))
        lo, hi = sorted((fy, ty))
        return all(board[y][fx] == EMPTY for y in range(lo + 1, hi))

    if kind == "n":
        # 马：日字，蹩马腿
        ady, adx = abs(dy), abs(dx)
        if not ((ady == 1 and adx == 2) or (ady == 2 and adx == 1)):
            return False
        if ady == 2:
            # 纵向走 2，马腿在 (fy + 方向, fx)
            return board[fy + _sign(dy)][fx] == EMPTY
        # 横向走 2，马腿在 (fy, fx + 方向)
        return board[fy][fx + _sign(dx)] == EMPTY

    if kind == "b":
        # 相/象：不过河、田字、塞象眼
        red = is_red(piece)
        if red and ty < 5:
            return False
        if not red and ty > 4:
            return False
        if abs(dy) != 2 or abs(dx) != 2:
            return False
        return board[(fy + ty) // 2][(fx + tx) // 2] == EMPTY

    if kind == "a":
        # 仕/士：九宫内斜走一格
        if not (3 <= tx <= 5):
            return False
        red = is_red(piece)
        if red and ty < 7:
            return False
        if not red and ty > 2:
            return False
        return abs(dy) == 1 and abs(dx) == 1

    if kind == "k":
        # 将/帅：九宫内直走一格
        if not (3 <= tx <= 5):
            return False
        red = is_red(piece)
        if red and ty < 7:
            return False
        if not red and ty > 2:
            return False
        return (abs(dy) == 1 and dx == 0) or (dy == 0 and abs(dx) == 1)

    if kind == "c":
        # 炮：直线；移动需路径无子且落空，吃子需恰好一个炮架且落点有子
        if fy != ty and fx != tx:
            return False
        if fy == ty:
            lo, hi = sorted((fx, tx))
            count = sum(1 for x in range(lo + 1, hi) if board[fy][x] != EMPTY)
        else:
            lo, hi = sorted((fy, ty))
            count = sum(1 for y in range(lo + 1, hi) if board[y][fx] != EMPTY)
        if count == 1 and target != EMPTY:
            return True
        return count == 0 and target == EMPTY

    if kind == "p":
        # 卒/兵
        if piece == "p":
            # 黑卒：未过河（y<5）只能向前 y+1；过河后可左右
            if fy < 5:
                return fx == tx and dy == 1
            return (fx == tx and dy == 1) or (fy == ty and abs(dx) == 1)
        # 红兵：未过河（y>=5）只能向前 y-1；过河后可左右
        if fy >= 5:
            return fx == tx and dy == -1
        return (fx == tx and dy == -1) or (fy == ty and abs(dx) == 1)

    return False


def pseudo_moves(board: List[List[str]], y: int, x: int) -> List[Point]:
    """棋子的全部伪合法走法。"""
    result = []
    for ty in range(ROWS):
        for tx in range(COLS):
            if can_move(board, y, x, ty, tx):
                result.append((ty, tx))
    return result


def legal_moves(board: List[List[str]], y: int, x: int) -> List[Point]:
    """棋子的全部合法走法（过滤送将/照面）。"""
    piece = board[y][x]
    if piece == EMPTY:
        return []
    red = is_red(piece)
    result = []
    for ty, tx in pseudo_moves(board, y, x):
        nb = apply_move(board, coords_to_move(y, x, ty, tx))
        if not in_check(nb, red):
            result.append((ty, tx))
    return result


def attackers(board: List[List[str]], y: int, x: int, by_red: bool) -> List[Point]:
    """攻击位置 (y,x) 的 by_red 方棋子坐标列表。"""
    result = []
    for fy, fx, p in list_pieces(board, by_red):
        if can_move(board, fy, fx, y, x):
            result.append((fy, fx))
    return result


def is_attacked(board: List[List[str]], y: int, x: int, by_red: bool) -> bool:
    """位置 (y,x) 是否被 by_red 方攻击（不含将帅照面，见 in_check）。"""
    for fy, fx, _ in list_pieces(board, by_red):
        if can_move(board, fy, fx, y, x):
            return True
    return False


def generals_face(board: List[List[str]]) -> bool:
    """将帅是否照面（同列且中间无子）。"""
    rk = find_king(board, True)
    bk = find_king(board, False)
    if not rk or not bk or rk[1] != bk[1]:
        return False
    x = rk[1]
    lo, hi = sorted((rk[0], bk[0]))
    return all(board[y][x] == EMPTY for y in range(lo + 1, hi))


def in_check(board: List[List[str]], red: bool) -> bool:
    """red 方将/帅是否正被将军（含将帅照面）。"""
    king = find_king(board, red)
    if not king:
        return False
    ky, kx = king
    if is_attacked(board, ky, kx, by_red=not red):
        return True
    return generals_face(board)


def has_legal_move(board: List[List[str]], red: bool) -> bool:
    """red 方是否还存在任一合法走法。"""
    for y, x, _ in list_pieces(board, red):
        if legal_moves(board, y, x):
            return True
    return False


def is_checkmate(board: List[List[str]], red: bool) -> bool:
    """red 方是否被将死（被将军且无合法走法）。"""
    return in_check(board, red) and not has_legal_move(board, red)


def is_stalemate(board: List[List[str]], red: bool) -> bool:
    """red 方是否困毙（未被将军但无合法走法）。"""
    return not in_check(board, red) and not has_legal_move(board, red)
