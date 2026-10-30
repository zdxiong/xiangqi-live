"""盘面客观事实快照层。

职责：在意图判断之前，把一个棋盘的全部可严格计算的客观事实一次性算清，
走前、走后各取一次快照，意图分类器只消费快照字段，不再零散临时计算。

单个快照包含（红黑双方各一份）：
    - 是否被将军
    - 全部合法走法（行棋空间）
    - 每个棋子的有根 / 无根
    - 每个棋子是否被攻击（被抓）
    - 每个棋子是否面临真实被吃威胁（real threat，过滤交换不划算的假攻击）

走前走后对比（compare）额外给出：是否少子、被吃棋子及其位置与归属。
另提供 move_verb：按移动方向生成中文着法叫法（进/退/平/飞/补/落等）。

坐标契约：board[y][x]，y=0 黑方底线 … y=9 红方底线；着法 rank 从红方
底线起算（y=9-rank）。红方向 y 减小处行棋，黑方向 y 增大处行棋。
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from .board import (
    COLS, ROWS, Point, apply_move, coords_to_move, find_king,
    in_bounds, list_pieces, parse_move,
)
from .pieces import EMPTY, is_red, material_value, piece_name
from .rules import attackers, can_move, in_check, is_attacked, legal_moves

DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


# ---------------------------------------------------------------- 基础事实

def can_reach(board: List[List[str]], fy: int, fx: int, ty: int, tx: int) -> bool:
    """几何可达（忽略落点归属），用于有根/保护判断。

    用虚拟敌子替换落点，使 can_move 的归属与炮架逻辑正常工作，返回前恢复。
    """
    piece = board[fy][fx]
    if piece == EMPTY:
        return False
    virtual = "x" if is_red(piece) else "X"
    saved = board[ty][tx]
    board[ty][tx] = virtual
    try:
        return can_move(board, fy, fx, ty, tx)
    finally:
        board[ty][tx] = saved


def protected_by(board: List[List[str]], y: int, x: int) -> List[Point]:
    """保护该子的同方其他子位置（有根依据）。"""
    red = is_red(board[y][x])
    out = []
    for fy, fx, _ in list_pieces(board, red):
        if (fy, fx) == (y, x):
            continue
        if can_reach(board, fy, fx, y, x):
            out.append((fy, fx))
    return out


def real_threat(board: List[List[str]], y: int, x: int) -> bool:
    """该子是否面临真实被吃威胁。

    遍历每个攻击者并模拟其吃子：若攻击者落点会被己方吃回，且攻击者
    价值不低于受害者（等价或亏本交换，对方占不到便宜），则该攻击不
    构成真实威胁；只有对方能白吃或净赚时才构成。
    """
    piece = board[y][x]
    if piece == EMPTY:
        return False
    if piece.lower() == "k":
        # 将帅（王）的"被吃"由被将军表达，不参与被抓/威胁
        return False
    red = is_red(piece)
    victim_val = material_value(piece, y)
    for ay, ax in attackers(board, y, x, not red):
        atk_val = material_value(board[ay][ax], ay)
        nb = apply_move(board, coords_to_move(ay, ax, y, x))
        if is_attacked(nb, y, x, red) and atk_val >= victim_val:
            continue
        return True
    return False


def pos_label(y: int, x: int) -> str:
    """坐标 -> UCI 位置字符串。"""
    return f"{chr(ord('a') + x)}{9 - y}"


# ---------------------------------------------------------------- 数据结构

@dataclass
class PieceFact:
    """单个棋子的客观事实。"""
    pos: str
    y: int
    x: int
    piece: str
    name_cn: str
    side: str                      # red / black
    legal_moves: List[str]         # 该子全部合法着法（行棋空间）
    rooted: bool                   # 有根
    protected_by: List[str]        # 保护者位置
    attacked_by: List[str]         # 攻击者位置（被抓，几何攻击）
    real_threat: bool              # 真实被吃威胁


@dataclass
class SideFact:
    """一方的盘面事实。"""
    side: str
    in_check: bool
    piece_count: int
    legal_move_count: int
    legal_moves: List[str]
    rooted: List[str]
    unrooted: List[str]
    attacked: List[str]            # 真实被抓（被捉）：敌子可白吃或交换获利
    pieces: List[PieceFact]


@dataclass
class Snapshot:
    """整个盘面的客观事实快照。"""
    total_pieces: int
    red: SideFact
    black: SideFact

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MoveChange:
    """走前走后对比（吃子信息）。"""
    move: str
    captured: bool
    captured_piece: str
    captured_name: str
    captured_pos: str
    captured_side: str             # red / black / 空
    before_count: int
    after_count: int

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- 取快照

def _side_snapshot(board: List[List[str]], red: bool) -> SideFact:
    side = "red" if red else "black"
    piece_facts: List[PieceFact] = []
    all_legal: List[str] = []
    rooted: List[str] = []
    unrooted: List[str] = []
    attacked: List[str] = []

    for y, x, piece in list_pieces(board, red):
        moves = [
            coords_to_move(y, x, ty, tx)
            for ty, tx in legal_moves(board, y, x)
        ]
        all_legal.extend(moves)

        protectors = protected_by(board, y, x)
        is_rooted = bool(protectors)
        is_king = piece.lower() == "k"
        foes = attackers(board, y, x, not red)
        is_real = real_threat(board, y, x)

        # 将帅（王）不能被吃、无保护概念，不参与有根/无根归类
        if not is_king:
            if is_rooted:
                rooted.append(pos_label(y, x))
            else:
                unrooted.append(pos_label(y, x))
        # 被抓=真实捉（敌子可白吃或交换获利）；几何瞄着只留在单子 attacked_by
        if is_real:
            attacked.append(pos_label(y, x))

        piece_facts.append(PieceFact(
            pos=pos_label(y, x), y=y, x=x, piece=piece,
            name_cn=piece_name(piece), side=side, legal_moves=moves,
            rooted=is_rooted,
            protected_by=[pos_label(py, px) for py, px in protectors],
            attacked_by=[pos_label(ay, ax) for ay, ax in foes],
            real_threat=is_real,
        ))

    return SideFact(
        side=side, in_check=in_check(board, red),
        piece_count=len(piece_facts), legal_move_count=len(all_legal),
        legal_moves=all_legal, rooted=rooted, unrooted=unrooted,
        attacked=attacked,
        pieces=piece_facts,
    )


def take_snapshot(board: List[List[str]]) -> Snapshot:
    """对当前棋盘计算完整客观事实快照（红黑双方）。"""
    return Snapshot(
        total_pieces=len(list_pieces(board)),
        red=_side_snapshot(board, True),
        black=_side_snapshot(board, False),
    )


def compare(board: List[List[str]], new_board: List[List[str]],
            move: str) -> MoveChange:
    """对比走前走后，给出少子/被吃棋子信息。"""
    before_count = len(list_pieces(board))
    after_count = len(list_pieces(new_board))
    # 被吃子即走前终点上的敌子（走后该位置被移动子占据）
    _, _, ty, tx = parse_move(move)
    cap_pos = pos_label(ty, tx)
    cap_piece = board[ty][tx]
    captured = cap_piece != EMPTY
    return MoveChange(
        move=move, captured=captured,
        captured_piece=cap_piece if captured else "",
        captured_name=piece_name(cap_piece) if captured else "",
        captured_pos=cap_pos if captured else "",
        captured_side=("black" if not is_red(cap_piece) else "red")
        if captured else "",
        before_count=before_count, after_count=after_count,
    )


# ---------------------------------------------------------------- 中文叫法

def move_verb(piece: str, fy: int, fx: int, ty: int, tx: int,
              captured: bool) -> str:
    """按移动方向生成中文着法叫法（不含序号/列名，仅动作词）。

    方向以行棋方自身为准：红方 dy<0 为前进，黑方 dy>0 为前进。
    """
    kind = piece.lower()
    red = is_red(piece)
    dy = ty - fy
    forward = (dy < 0) if red else (dy > 0)
    horizontal = (dy == 0)

    if kind == "p":
        # 兵/卒：向前 进/拱；左右 平（无退）
        return f"平{piece_name(piece)}" if horizontal else f"进{piece_name(piece)}"

    if kind == "c":
        # 炮：吃子（中间有架）= 飞炮；否则 进/退/平
        if captured:
            return "飞炮吃子"
        if horizontal:
            return "平炮"
        return "进炮" if forward else "退炮"

    if kind == "n":
        # 马：向前 进马；向后 回马（退马/倒马）
        return "进马" if forward else "回马"

    if kind == "r":
        # 车：左右 平车；向前 进车；向后 退车
        if horizontal:
            return "平车"
        return "进车" if forward else "退车"

    if kind == "b":
        # 相/象：向前（向上）飞象；向后（向下）回象
        return "飞象" if forward else "回象"

    if kind == "a":
        # 仕/士：向前（向上）补士/进士；向后（向下）落士/退士
        return "补士" if forward else "落士"

    if kind == "k":
        # 将/帅：左右 出将；向前（向上）进将；向后（向下）落将
        if horizontal:
            return "出将"
        return "进将" if forward else "落将"

    return piece_name(piece)
