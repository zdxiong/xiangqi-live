"""象棋战术意图分析器（结构化、全招法覆盖、基于盘面事实快照）。

工作方式（严格两阶段）：
    1. 走前、走后各调用 snapshot.take_snapshot 取一次完整客观事实快照，
       并用 snapshot.compare 得到吃子对比、snapshot.move_verb 得到中文叫法。
    2. 分类器只消费快照字段（被将军、全部合法走法、有根/无根、被抓、
       真实威胁），按显式优先级链判断意图，不再零散临时计算。

设计原则：
    - 只基于可严格计算的客观事实，不做"理论威胁"的静态臆测；
    - 任何合法走法都有标签，安静步兜底为"调运"；
    - 每条结论附带可人工复核的 reasons，页面同时展示完整事实快照。

坐标契约：board[y][x]，y=0 黑方底线 … y=9 红方底线；着法 rank 从红方
底线起算（y=9-rank），由 board.parse_move 负责转换。
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .board import (
    COLS, ROWS, Point, apply_move, coords_to_move, find_king,
    in_bounds, list_pieces, parse_move,
)
from .pieces import (
    EMPTY, has_crossed_river, is_pawn, is_red, material_value, piece_name,
)
from .rules import (
    attackers, can_move, in_check, is_checkmate, is_stalemate,
    is_attacked, pseudo_moves,
)
from .snapshot import (
    MoveChange, Snapshot, can_reach, compare, move_verb, pos_label,
    protected_by, real_threat, take_snapshot,
)

DIRS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

PHASE_CN = {"opening": "开局", "middle": "中局", "endgame": "残局"}

# 大类（页面配色依据）
CATEGORY = {
    "mate": "杀攻",
    "defense": "防御",
    "capture": "吃兑",
    "threat": "威胁",
    "position": "位置",
    "development": "调运",
    "invalid": "非法",
}

# 开局谱（中文着法首词 -> 开局名），仅开局阶段命中
OPENINGS = {
    "炮二平五": "当头炮", "炮八平五": "当头炮",
    "兵三进一": "仙人指路", "兵七进一": "仙人指路",
    "相三进五": "飞相局", "相七进五": "飞相局",
    "马二进三": "起马局", "马八进七": "起马局",
    "炮八进二": "左炮巡河",
    "炮二平六": "过宫炮", "炮八平六": "过宫炮",
    "炮二平四": "仕角炮",
}


# ---------------------------------------------------------------- 数据结构

@dataclass
class IntentResult:
    """单步着法的结构化意图。"""
    move: str = ""
    valid: bool = True
    phase: str = "middle"
    piece_cn: str = ""
    from_pos: str = ""
    to_pos: str = ""
    captured_cn: str = ""
    move_verb_cn: str = ""
    category_code: str = ""
    category_cn: str = ""
    primary_code: str = ""
    primary_cn: str = ""
    primary_detail: str = ""
    opening_cn: str = ""
    tags_cn: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    pv_preview: List[str] = field(default_factory=list)
    facts: Dict = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict:
        """转前端 JSON（驼峰字段，兼容旧版契约，新增 facts/moveVerb）。"""
        return {
            "move": self.move,
            "valid": self.valid,
            "phase": self.phase,
            "phaseCn": PHASE_CN.get(self.phase, self.phase),
            "pieceCn": self.piece_cn,
            "fromPos": self.from_pos,
            "toPos": self.to_pos,
            "capturedCn": self.captured_cn,
            "moveVerb": self.move_verb_cn,
            "categoryCode": self.category_code,
            "categoryCn": self.category_cn,
            "primaryCode": self.primary_code,
            "primaryCn": self.primary_cn,
            "primaryDetail": self.primary_detail,
            "openingCn": self.opening_cn,
            "tagsCn": self.tags_cn,
            "reasons": self.reasons,
            "pvPreview": self.pv_preview,
            "facts": self.facts,
            "summary": self.summary,
        }


# ----------------------------------------------------- 战术专用事实函数

def detect_phase(board: List[List[str]], fen: Optional[str] = None) -> str:
    """阶段：棋子总数 + FEN 全回合数。"""
    total = len(list_pieces(board))
    fullmove = None
    if fen:
        parts = fen.split()
        if len(parts) >= 6:
            try:
                fullmove = int(parts[5])
            except ValueError:
                fullmove = None
    if total >= 26 and (fullmove is None or fullmove <= 8):
        return "opening"
    if total <= 16:
        return "endgame"
    return "middle"


def find_pins(board: List[List[str]], red: bool) -> List[Tuple[Point, Point, Point]]:
    """red 方直线子形成的牵制：(牵制子, 被牵制子, 后方目标)。"""
    pins = []
    for y, x, p in list_pieces(board, red):
        if p.lower() not in ("r", "c"):
            continue
        for dy, dx in DIRS4:
            cy, cx = y + dy, x + dx
            first = None
            while in_bounds(cy, cx):
                cell = board[cy][cx]
                if cell != EMPTY:
                    if first is None:
                        if is_red(cell) == red:
                            break
                        first = (cy, cx, cell)
                    else:
                        if is_red(cell) != red:
                            if cell.lower() == "k" or \
                                    material_value(cell) > material_value(first[2]):
                                pins.append(((y, x), (first[0], first[1]), (cy, cx)))
                        break
                cy += dy
                cx += dx
    return pins


def has_mate_in_one(board: List[List[str]], red: bool) -> bool:
    """red 方下一步是否存在将死对方的走法（二步深度客观模拟）。"""
    for y, x, _ in list_pieces(board, red):
        for ty, tx in pseudo_moves(board, y, x):
            nb = apply_move(board, coords_to_move(y, x, ty, tx))
            if is_checkmate(nb, not red):
                return True
    return False


def screen_piece(board: List[List[str]], src: Point, king_pos: Point) -> Optional[str]:
    """炮与王位之间唯一的炮架子（无则 None）。"""
    sy, sx = src
    ky, kx = king_pos
    if sy == ky:
        lo, hi = sorted((sx, kx))
        mid = [board[sy][i] for i in range(lo + 1, hi) if board[sy][i] != EMPTY]
    elif sx == kx:
        lo, hi = sorted((sy, ky))
        mid = [board[i][sx] for i in range(lo + 1, hi) if board[i][sx] != EMPTY]
    else:
        return None
    return mid[0] if len(mid) == 1 else None


def protecting_target(board: List[List[str]], new_board: List[List[str]],
                      ty: int, tx: int, red: bool) -> Optional[Point]:
    """移动子是否保护了某个走前确实需要保护的己方子。

    目标须满足：走前被攻击，且走前无根或面临真实威胁（即本来不保险）；
    若目标走前已有根且无真实威胁，则这步不是为了保它（如亮车）。
    """
    for y, x, _ in list_pieces(board, red):
        if (y, x) == (ty, tx):
            continue
        if not is_attacked(board, y, x, not red):
            continue
        already_rooted = bool(protected_by(board, y, x))
        if already_rooted and not real_threat(board, y, x):
            continue
        if can_reach(new_board, ty, tx, y, x):
            return y, x
    return None


def find_skewer(board: List[List[str]], ty: int, tx: int,
                red: bool) -> Optional[Tuple[Point, Point]]:
    """车在落点沿同一射线串打两个无根敌子（近子, 远子）。

    近子与远子在一条直线上、中间无遮挡且都无根：对方逃近子后，车可沿
    该线吃远子，二者无法两全。检查远子的根时临时移除近子——若远子只
    被近子保护，近子被吃后该根即失效，仍算无根。炮的串打暂不纳入。
    """
    if board[ty][tx].lower() != "r":
        return None
    for dy, dx in DIRS4:
        cy, cx = ty + dy, tx + dx
        first: Optional[Point] = None
        while in_bounds(cy, cx):
            cell = board[cy][cx]
            if cell != EMPTY:
                if is_red(cell) == red:
                    break  # 己方子挡住射线
                if first is None:
                    first = (cy, cx)
                else:
                    second = (cy, cx)
                    # 近子本身无根
                    if protected_by(board, first[0], first[1]):
                        break
                    # 近子被移除后，远子是否还有别的保护者
                    saved = board[first[0]][first[1]]
                    board[first[0]][first[1]] = EMPTY
                    try:
                        far_rooted = bool(
                            protected_by(board, second[0], second[1]))
                    finally:
                        board[first[0]][first[1]] = saved
                    if not far_rooted:
                        return first, second
                    break
            cy += dy
            cx += dx
    return None


def blockade_target(board: List[List[str]], ty: int, tx: int, red: bool) -> Optional[Point]:
    """直线子紧邻压制对方边线子（敌子背后即棋盘边界，无处可退）。"""
    if board[ty][tx].lower() not in ("r", "c"):
        return None
    for dy, dx in DIRS4:
        cy, cx = ty + dy, tx + dx
        if in_bounds(cy, cx) and board[cy][cx] != EMPTY \
                and is_red(board[cy][cx]) != red:
            if not in_bounds(cy + dy, cx + dx):
                return cy, cx
    return None


# ----------------------------------------------------- 快照摘要（给前端）

def _side_brief(sf) -> Dict:
    return {
        "side": sf.side,
        "inCheck": sf.in_check,
        "legalMoveCount": sf.legal_move_count,
        "rooted": sf.rooted,
        "unrooted": sf.unrooted,
        "attacked": sf.attacked,
    }


def _facts_brief(before: Snapshot, after: Snapshot, change: MoveChange) -> Dict:
    return {
        "before": {"red": _side_brief(before.red),
                   "black": _side_brief(before.black)},
        "after": {"red": _side_brief(after.red),
                  "black": _side_brief(after.black)},
        "change": change.to_dict(),
    }


# ---------------------------------------------------------------- 主分类器

def analyze_intent(board: List[List[str]], move: str,
                   fen: Optional[str] = None,
                   move_cn: Optional[str] = None,
                   pv_preview: Optional[List[str]] = None) -> IntentResult:
    """分析单步着法的战术意图，返回结构化 IntentResult。"""
    res = IntentResult(move=move, pv_preview=list(pv_preview or []))
    phase = detect_phase(board, fen)
    res.phase = phase

    # 非法着法：不硬算，直接返回
    try:
        fy, fx, ty, tx = parse_move(move)
    except ValueError as e:
        res.valid = False
        res.category_code = "invalid"
        res.category_cn = CATEGORY["invalid"]
        res.primary_code = "invalid"
        res.primary_cn = "非法着法"
        res.primary_detail = str(e)
        res.reasons = [f"着法解析失败：{e}"]
        res.summary = f"着法 {move} 非法"
        return res

    piece = board[fy][fx]
    if piece == EMPTY or not can_move(board, fy, fx, ty, tx):
        res.valid = False
        res.category_code = "invalid"
        res.category_cn = CATEGORY["invalid"]
        res.primary_code = "invalid"
        res.primary_cn = "非法着法"
        res.primary_detail = "起点无子或该走法不符合棋规"
        res.reasons = [
            f"起点 {pos_label(fy, fx)} 棋子："
            f"{piece_name(piece) if piece != EMPTY else '空'}",
            "can_move 校验不通过（含蹩腿/塞象眼/路径阻挡/落点归属）",
        ]
        res.summary = f"着法 {move} 非法"
        return res

    kind = piece.lower()
    red = is_red(piece)
    new_board = apply_move(board, move)

    # ===== 走前 / 走后完整事实快照 + 吃子对比 + 中文叫法 =====
    before = take_snapshot(board)
    after = take_snapshot(new_board)
    change = compare(board, new_board, move)
    res.facts = _facts_brief(before, after, change)

    self_cn = "红方" if red else "黑方"
    enemy_cn = "黑方" if red else "红方"
    res.piece_cn = piece_name(piece)
    res.from_pos = pos_label(fy, fx)
    res.to_pos = pos_label(ty, tx)
    res.move_verb_cn = move_verb(piece, fy, fx, ty, tx, change.captured)
    if change.captured:
        res.captured_cn = change.captured_name

    # 从快照派生：己方/敌方 side 事实
    my_before = before.red if red else before.black
    en_after = after.black if red else after.red
    my_after = after.red if red else after.black

    # 移动子在走后快照中的事实，以及它攻击的敌方棋子（敌方棋子 attacked_by 含移动子）
    my_pf = next((pf for pf in my_after.pieces if pf.pos == res.to_pos), None)
    spot_attacked = bool(my_pf.attacked_by) if my_pf else False
    tg_pieces = [pf for pf in en_after.pieces if res.to_pos in pf.attacked_by]
    # 排除敌王（将军单独处理）
    tg_pieces = [pf for pf in tg_pieces if pf.piece.lower() != "k"]
    real_tg = [pf for pf in tg_pieces if pf.real_threat]

    # 将军来源：走后敌方王的 attacked_by
    en_king_pf = next((pf for pf in en_after.pieces
                       if pf.piece.lower() == "k"), None)
    sources = list(en_king_pf.attacked_by) if en_king_pf else []
    old_self_check = my_before.in_check
    new_enemy_check = en_after.in_check

    # 通用事实（reasons 基座）
    base_reasons = [
        f"阶段：{PHASE_CN[phase]}（棋盘 {before.total_pieces} 子）",
        f"移动子：{self_cn}{res.piece_cn} {res.from_pos}→{res.to_pos}"
        f"（叫法：{res.move_verb_cn}）",
    ]
    if change.captured:
        base_reasons.append(
            f"吃子：对方{change.captured_name}（{change.captured_pos}），"
            f"价值 {material_value(change.captured_piece, ty)}"
        )
    else:
        base_reasons.append("吃子：无（走前后棋子数 "
                            f"{change.before_count}→{change.after_count}）")

    def finish(category_code, primary_code, primary_cn, detail,
               extra_reasons, tags=None, opening=""):
        res.category_code = category_code
        res.category_cn = CATEGORY[category_code]
        res.primary_code = primary_code
        res.primary_cn = primary_cn
        res.primary_detail = detail
        res.tags_cn = list(tags or [])
        res.opening_cn = opening
        res.reasons = base_reasons + extra_reasons
        res.summary = f"{self_cn}{res.piece_cn}：{primary_cn}"
        return res

    def nm(pf):
        return piece_name(pf.piece)

    # ── 1. 终局：将死 / 困毙 ──
    if is_checkmate(new_board, not red):
        return finish(
            "mate", "checkmate", "将死",
            f"{self_cn}走后{enemy_cn}被将军且无合法走法，对局结束",
            [f"走后{enemy_cn}被将军", f"{enemy_cn}无任何合法走法（将死）"],
            tags=["杀棋"],
        )
    if is_stalemate(new_board, not red):
        return finish(
            "mate", "stalemate", "困毙",
            f"{enemy_cn}未被将军但无合法走法，困毙判负",
            [f"走后{enemy_cn}未被将军", f"{enemy_cn}无任何合法走法（困毙）"],
        )

    # ── 2. 应将（走前己方被将军，首要意图是解将）──
    if old_self_check:
        # 将军来源（走前己方王的 attacked_by）
        self_king_pf = next((pf for pf in my_before.pieces
                             if pf.piece.lower() == "k"), None)
        checkers = self_king_pf.attacked_by if self_king_pf else []
        if change.captured and res.to_pos in checkers:
            return finish(
                "defense", "capture_checker", "吃子解将",
                f"吃掉正在将军的{res.captured_cn}，解除己方将军",
                ["走前己方被将军", f"被吃子{res.captured_cn}是将军来源",
                 "走后己方不再被将军"],
            )
        if kind == "k":
            return finish(
                "defense", "king_evade", "躲将",
                "移动将帅避开将军线",
                ["走前己方被将军", "移动将帅，走后不被将军"],
            )
        return finish(
            "defense", "block_check", "垫将",
            "棋子挡在将军线路上化解将军",
            ["走前己方被将军", "未吃子、未动将帅",
             "挡在将军路径上，走后不被将军"],
        )

    # ── 3. 将军（走后对方被将军）──
    if new_enemy_check:
        extra = [f"走后{enemy_cn}被将军", f"将军来源 {len(sources)} 个"]
        if len(sources) >= 2:
            return finish("mate", "double_check", "双将",
                          f"两个子同时将军，{enemy_cn}只能动将",
                          extra + [f"将军来源：{len(sources)} 个子"],
                          tags=["将军"])
        if real_tg:
            names = "、".join(nm(pf) for pf in real_tg)
            return finish("mate", "check_capture", f"将军抽吃（{names}）",
                          f"将军同时威胁吃掉对方{names}",
                          extra + [f"移动子另可吃真实威胁目标：{names}"],
                          tags=["将军", "抽吃"])
        if res.to_pos not in sources:
            return finish("mate", "discovered_check", "闪将",
                          "让开线路露出后方子将军",
                          extra + ["将军来源是后方棋子，移动子让开线路"],
                          tags=["闪将", "将军"])
        # 马后炮 / 重炮
        if en_king_pf:
            king_xy = (en_king_pf.y, en_king_pf.x)
            for src_pos in sources:
                sy, sx = _pos_to_xy(src_pos)
                if new_board[sy][sx].lower() == "c":
                    screen = screen_piece(new_board, (sy, sx), king_xy)
                    if screen:
                        if screen.upper() == "N":
                            return finish("mate", "royal_cannon", "马后炮",
                                          "炮以马为架将军，形成马后炮",
                                          extra + ["炮架为对方马"],
                                          tags=["将军"])
                        if screen.upper() == "C":
                            return finish("mate", "double_cannon", "重炮",
                                          "两炮重叠将军，形成重炮",
                                          extra + ["炮架为对方炮"],
                                          tags=["将军"])
        return finish("mate", "check", "将军",
                      f"走后{enemy_cn}被将军", extra, tags=["将军"])

    # ── 4. 吃子（落点为敌子，且未将军）──
    if change.captured:
        cap_val = material_value(change.captured_piece, ty)
        our_val = material_value(piece, fy)
        if spot_attacked and our_val > cap_val:
            return finish(
                "capture", "sacrifice", f"弃子（送{res.piece_cn}）",
                f"吃{res.captured_cn}后{res.piece_cn}处于被攻位置，主动弃子",
                [f"我方{res.piece_cn}价值 {our_val} > 被吃子 {cap_val}",
                 "落点被对方攻击，存在被吃回风险"],
            )
        if spot_attacked and abs(our_val - cap_val) <= max(100, our_val * 0.25):
            return finish(
                "capture", "trade", f"兑子（兑{res.captured_cn}）",
                "等价交换，双方子力价值相当",
                [f"我方 {our_val} vs 被吃子 {cap_val}，价值相当",
                 "落点被对方攻击，可被等价吃回"],
            )
        if cap_val > our_val:
            return finish(
                "capture", "winning_exchange",
                f"换子有利（吃{res.captured_cn}）",
                f"以{res.piece_cn}吃掉价值更高的{res.captured_cn}",
                [f"被吃子 {cap_val} > 我方 {our_val}",
                 "以小吃大，子力占优"],
            )
        return finish(
            "capture", "capture", f"吃子（吃{res.captured_cn}）",
            f"{res.piece_cn}吃掉对方{res.captured_cn}，获得子力",
            [f"被吃子价值 {cap_val}",
             "落点被对方攻击" if spot_attacked else "落点未被对方攻击"],
        )

    # ── 5. 开局名（开局阶段命中开局谱，优先于捉子等软关系）──
    first_cn = (move_cn or "").split()[0] if move_cn else ""
    if phase == "opening" and first_cn in OPENINGS:
        return finish(
            "development", "opening", f"开局·{OPENINGS[first_cn]}",
            f"命中开局谱：{OPENINGS[first_cn]}",
            [f"中文着法 {first_cn} 命中开局谱"],
            opening=OPENINGS[first_cn],
        )

    # ── 6. 叫杀（二步深度模拟）──
    if has_mate_in_one(new_board, red):
        return finish(
            "threat", "threat_mate", "叫杀",
            f"虽未将军，但下一步存在将死{enemy_cn}的走法",
            ["走后不将军", "模拟己方全部下一步走法，存在将死"],
        )

    # ── 串打：车沿一条线串着两个无根敌子，逃近子吃远子（优先于捉双/捉单）──
    sk = find_skewer(new_board, ty, tx, red)
    if sk:
        near, far = sk
        near_n = piece_name(new_board[near[0]][near[1]])
        far_n = piece_name(new_board[far[0]][far[1]])
        return finish(
            "threat", "skewer", f"串打（{near_n}、{far_n}）",
            "两子在同一直线且无根，对方逃近子后可沿该线吃远子",
            [f"近子{near_n}（{pos_label(near[0], near[1])}）、远子{far_n}"
             f"（{pos_label(far[0], far[1])}）共线且均无根",
             "对方逃近子后，移动子可沿该线吃远子，二者无法两全"],
        )

    # ── 7. 捉双 / 捉子（移动子威胁真实可吃目标）──
    if len(real_tg) >= 2:
        names = "、".join(nm(pf) for pf in real_tg)
        return finish(
            "threat", "fork", f"捉双（{names}）",
            f"移动子同时威胁 {len(real_tg)} 个真实可吃目标",
            [f"可同时吃真实目标：{names}"],
        )
    if len(real_tg) == 1:
        pf = real_tg[0]
        return finish(
            "threat", "hunt", f"捉子（捉{nm(pf)}）",
            f"下一步可吃对方{nm(pf)}",
            [f"攻击目标{nm(pf)}构成真实吃子威胁"],
        )

    # ── 8. 牵制（走后新形成 pin，且牵制子为移动子，优先于压马）──
    for pinner, pinned, behind in find_pins(new_board, red):
        if pinner == (ty, tx):
            return finish(
                "threat", "pin",
                f"牵制（{piece_name(new_board[pinned[0]][pinned[1]])}）",
                "对方子被牵制，移动将暴露后方目标",
                [f"被牵制子：{piece_name(new_board[pinned[0]][pinned[1]])}",
                 f"后方目标：{piece_name(new_board[behind[0]][behind[1]])}"],
            )

    # ── 逃子（走前自身面临真实威胁，走后安全）优先于压马 ──
    # 移动子自身难保、先退到安全点时，退路上对有根马的瞄着只是附带效果
    if real_threat(board, fy, fx) and not spot_attacked:
        return finish(
            "development", "flee", "逃子",
            f"{res.piece_cn}从被攻位置转移到安全点",
            ["走前该子面临真实被吃威胁", "走后落点不被攻击"],
        )

    # 压马：移动子自身不在逃时，车攻击有根马（有根不构成捉）
    if kind == "r" and any(pf.piece.upper() == "N" for pf in tg_pieces):
        return finish(
            "threat", "press", "压马",
            "车压制对方有根马（有根不构成捉）",
            ["攻击目标马有保护", "线路压制，限制其活动"],
        )

    # 保子：移动子掩护走前无保护/受真实威胁的己方被攻子
    pt = protecting_target(board, new_board, ty, tx, red)
    if pt:
        return finish(
            "development", "protect",
            f"保子（保{piece_name(new_board[pt[0]][pt[1]])}）",
            "移动子为原本无保护的被攻子补上根，对方不敢吃",
            [f"己方{piece_name(new_board[pt[0]][pt[1]])}正被攻击且走前无根/受威胁",
             "移动子可攻击到该位置，走后形成保护（有根）"],
        )

    # ── 10. 位置类客观事实 ──
    if is_pawn(piece) and has_crossed_river(piece, ty):
        return finish(
            "position", "cross_river", "过河",
            f"{res.piece_cn}越过河界进入对方半场",
            ["兵卒过河，活动能力增强"],
        )
    if tx == 4:
        return finish(
            "position", "center", "控制中路",
            "落子中路（x=4），控制中线",
            ["落点在中路纵线"],
        )
    if (red and ty < 5) or (not red and ty > 4):
        return finish(
            "position", "river_press", "压制河界",
            "进入对方半场，形成前压",
            ["落点越过河界进入对方半场"],
        )
    if kind == "r" and tx in (3, 5):
        return finish(
            "position", "key_point", "抢占肋道",
            "车占肋道，控制关键线路",
            [f"落点 x={tx} 为肋道要点"],
        )
    blk = blockade_target(new_board, ty, tx, red)
    if blk:
        return finish(
            "position", "blockade", "封锁",
            "直线压制对方边线子，使其无路可退",
            [f"紧邻对方{piece_name(new_board[blk[0]][blk[1]])}，"
             "其背后为棋盘边界"],
        )

    # ── 11. 出动大子 / 上士飞象 ──
    if phase == "opening" and kind in ("r", "n", "c"):
        return finish(
            "development", "develop", "出动大子",
            f"开局阶段出动{res.piece_cn}，抢占主动",
            ["开局阶段，大子（车马炮）移动"],
        )
    if kind in ("a", "b"):
        return finish(
            "development", "setup",
            "上士固防" if kind == "a" else "飞象固防",
            "巩固阵型、加强防守",
            [f"移动子为{res.piece_cn}，属防御性布置"],
        )

    # ── 12. 兜底：调运（安静步，保证 100% 覆盖）──
    return finish(
        "development", "redeploy", "调运",
        "无吃子/将军/捉子等客观事件，属子力调运",
        ["无吃子、无将军、无新攻击关系", "客观事实均不命中，落调运兜底"],
    )


def _pos_to_xy(pos: str) -> Point:
    """UCI 位置字符串 -> (y,x)。"""
    x = ord(pos[0]) - ord("a")
    y = 9 - int(pos[1])
    return y, x
