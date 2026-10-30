"""意图分析验证脚本（不依赖 pytest，可直接运行）。

覆盖：
  1. 初始棋盘全部合法走法：无异常、100% 有标签、reasons 非空；
  2. 典型局面：将军/将死/吃子/兑子/弃子/逃子/捉双/垫将/躲将/
     吃子解将/叫杀/牵制/过河/开局名/非法着法；
  3. 输出意图分布统计。

运行：
    cd xiangqi-live
    python scripts/verify_intent.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine import board as B
from app.engine import rules as R
from app.engine.intents import analyze_intent

_passed = 0
_failed = 0


def check(name, cond, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"[PASS] {name}")
    else:
        _failed += 1
        print(f"[FAIL] {name} {extra}")


def place(board, y, x, piece):
    board[y][x] = piece
    return board


def minimal_board():
    """只含红帅黑将的合法空棋盘（将帅不同列，避免照面）。"""
    b = B.new_board()
    place(b, 9, 3, "K")
    place(b, 0, 4, "k")
    return b


# ============================================================
# 1. 初始棋盘：全部合法走法覆盖
# ============================================================
ib = B.initial_board()
all_legal = []
for y, x, _ in B.list_pieces(ib, True):
    for ty, tx in R.legal_moves(ib, y, x):
        all_legal.append(B.coords_to_move(y, x, ty, tx))

print(f"初始棋盘红方合法走法数：{len(all_legal)}")
dist = Counter()
errors = []
for m in all_legal:
    try:
        r = analyze_intent(ib, m)
        if not r.valid or not r.primary_code or not r.category_code or not r.reasons:
            errors.append((m, "字段缺失"))
        dist[r.primary_code] += 1
    except Exception as e:
        errors.append((m, f"{type(e).__name__}: {e}"))

check("全部合法走法分析无异常且字段完整", not errors, str(errors[:5]))
print("意图分布：", dict(dist))

# 对方（黑方）合法走法同样覆盖
black_legal = []
for y, x, _ in B.list_pieces(ib, False):
    for ty, tx in R.legal_moves(ib, y, x):
        black_legal.append(B.coords_to_move(y, x, ty, tx))
black_errors = []
for m in black_legal:
    try:
        r = analyze_intent(ib, m)
        if not r.valid or not r.primary_code:
            black_errors.append(m)
    except Exception as e:
        black_errors.append(f"{m}: {e}")
check("黑方全部合法走法分析无异常", not black_errors, str(black_errors[:5]))

# ============================================================
# 2. 典型局面
# ============================================================

# ── 将军 check：红车 (2,4)→(1,4)，黑将有处走
b = minimal_board()
place(b, 2, 4, "R")
r = analyze_intent(b, "e7e8")
check("将军 check", r.primary_code == "check", r.primary_code)

# ── 将死 checkmate：车 (2,1)→(0,1)，另一车封 (1,5)
b = minimal_board()
place(b, 2, 1, "R")
place(b, 1, 5, "R")
r = analyze_intent(b, "b7b9")
check("将死 checkmate", r.primary_code == "checkmate", r.primary_code)

# ── 吃子 capture：车 (5,2)→(5,5) 吃黑卒
b = minimal_board()
place(b, 5, 2, "R")
place(b, 5, 5, "p")
r = analyze_intent(b, "c4f4")
check("吃子 capture", r.primary_code == "capture" and r.captured_cn == "卒",
      r.primary_code)

# ── 兑子 trade：车吃车，落点被另一黑车攻击
b = minimal_board()
place(b, 5, 2, "R")
place(b, 5, 5, "r")
place(b, 3, 5, "r")
r = analyze_intent(b, "c4f4")
check("兑子 trade", r.primary_code == "trade", r.primary_code)

# ── 弃子 sacrifice：车吃卒但落点被黑车攻击
b = minimal_board()
place(b, 5, 2, "R")
place(b, 5, 5, "p")
place(b, 3, 5, "r")
r = analyze_intent(b, "c4f4")
check("弃子 sacrifice", r.primary_code == "sacrifice", r.primary_code)

# ── 逃子 flee：被车攻的马跳到 (3,3)，新位置无攻击目标
b = minimal_board()
place(b, 5, 2, "N")
place(b, 5, 0, "r")
r = analyze_intent(b, "c4d6")
check("逃子 flee", r.primary_code == "flee", r.primary_code)

# ── 捉双 fork：车 (6,2)→(5,2) 同时威胁两个无根卒，不与黑将同线
b = minimal_board()
place(b, 6, 2, "R")
place(b, 5, 0, "p")
place(b, 5, 4, "p")
r = analyze_intent(b, "c3c4")
check("捉双 fork", r.primary_code == "fork", r.primary_code)

# ── 串打 skewer：红车 (3,2)→(4,2)，沿同列串着两个无根卒，逃一个吃另一个
b = minimal_board()
place(b, 3, 2, "R")
place(b, 5, 2, "p")
place(b, 6, 2, "p")
r = analyze_intent(b, "c6c5")
check("串打 skewer", r.primary_code == "skewer", r.primary_code)

# ── 垫将 block_check：黑车 (9,0) 将军，红车 (8,3)→(9,3) 挡
b = B.new_board()
place(b, 9, 4, "K")
place(b, 0, 3, "k")
place(b, 9, 0, "r")
place(b, 8, 3, "R")
r = analyze_intent(b, "d1d0")
check("垫将 block_check", r.primary_code == "block_check", r.primary_code)

# ── 躲将 king_evade：帅 (9,4)→(8,4)
b = B.new_board()
place(b, 9, 4, "K")
place(b, 0, 3, "k")
place(b, 9, 0, "r")
r = analyze_intent(b, "e0e1")
check("躲将 king_evade", r.primary_code == "king_evade", r.primary_code)

# ── 吃子解将 capture_checker：红车 (8,0) 吃将军黑车 (9,0)
b = B.new_board()
place(b, 9, 4, "K")
place(b, 0, 3, "k")
place(b, 9, 0, "r")
place(b, 8, 0, "R")
r = analyze_intent(b, "a1a0")
check("吃子解将 capture_checker", r.primary_code == "capture_checker",
      r.primary_code)

# ── 叫杀 threat_mate：车 (2,3)→(1,3)，下一步可将死（R2 在 (1,5) 封点）
b = B.new_board()
place(b, 9, 3, "K")
place(b, 0, 4, "k")
place(b, 2, 3, "R")
place(b, 1, 5, "R")
place(b, 4, 8, "p")  # 黑方有合法走法，避免被误判困毙
r = analyze_intent(b, "d7d8")
check("叫杀 threat_mate", r.primary_code == "threat_mate", r.primary_code)

# ── 牵制 pin：车 (3,3)→(2,3)，黑马 (1,3) 后方是黑将 (0,3)；
#    另布黑卒 (4,8) 保证黑方有合法走法，避免被误判困毙
b = B.new_board()
place(b, 9, 4, "K")
place(b, 0, 3, "k")
place(b, 1, 3, "n")
place(b, 3, 3, "R")
place(b, 4, 8, "p")
r = analyze_intent(b, "d6d7")
check("牵制 pin", r.primary_code == "pin", r.primary_code)

# ── 过河 cross_river：红兵 (5,2)→(4,2)
b = minimal_board()
place(b, 5, 2, "P")
r = analyze_intent(b, "c4c5")
check("过河 cross_river", r.primary_code == "cross_river", r.primary_code)

# ── 开局名 opening：红炮 h2→e2，炮二平五
b = B.initial_board()
r = analyze_intent(b, "h2e2", move_cn="炮二平五")
check("开局名 opening（当头炮）",
      r.primary_code == "opening" and r.opening_cn == "当头炮",
      r.primary_code)

# ── 非法着法 invalid：红车被兵挡住无法直走
b = B.initial_board()
r = analyze_intent(b, "a0a5")
check("非法着法 invalid", r.primary_code == "invalid" and not r.valid,
      r.primary_code)

# ============================================================
# 3. 汇总
# ============================================================
print(f"\n结果：{_passed} 通过，{_failed} 失败")
sys.exit(1 if _failed else 0)
