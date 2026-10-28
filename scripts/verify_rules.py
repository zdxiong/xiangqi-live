"""P3.1 棋盘与规则层验证脚本（不依赖 pytest，可直接运行）。

运行：
    cd xiangqi-live
    python scripts/verify_rules.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine import board as B
from app.engine import pieces as P
from app.engine import rules as R

_passed = 0
_failed = 0


def check(name: str, cond: bool, extra: str = ""):
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


# 1. 初始棋盘
ib = B.initial_board()
check("初始棋盘棋子数=32", len(B.list_pieces(ib)) == 32)
check("红帅在 (9,4)", B.find_king(ib, True) == (9, 4))
check("黑将在 (0,4)", B.find_king(ib, False) == (0, 4))

# 2. 红车走法（初始 (7,0) 为空，(6,0) 为红兵）
check("红车可前进一步到 (8,0)", R.can_move(ib, 9, 0, 8, 0))
check("红车可走到 (7,0)", R.can_move(ib, 9, 0, 7, 0))
check("红车不能走到己方兵位 (6,0)", not R.can_move(ib, 9, 0, 6, 0))
check("红车不能横走", not R.can_move(ib, 9, 0, 9, 2))

# 3. 红马走法（(9,1) 可跳 (7,0)、(7,2)，蹩腿点 (8,1) 为空）
check("红马可跳 (7,0)", R.can_move(ib, 9, 1, 7, 0))
check("红马可跳 (7,2)", R.can_move(ib, 9, 1, 7, 2))
check("红马不能走直线", not R.can_move(ib, 9, 1, 8, 1))

# 4. 红兵（未过河）
check("红兵可前进一步", R.can_move(ib, 6, 0, 5, 0))
check("未过河红兵不能横走", not R.can_move(ib, 6, 0, 6, 1))

# 5. 蹩马腿
mb = B.new_board()
place(mb, 5, 1, "N")
place(mb, 4, 1, "P")  # 马腿
check("无蹩腿时马可纵向跳", R.can_move(B.new_board() if False else
      (lambda b: (place(b, 5, 1, "N"), b)[1])(B.new_board()), 5, 1, 3, 2))
check("蹩马腿时不能纵向跳", not R.can_move(mb, 5, 1, 3, 2))
check("蹩纵向腿不影响横向跳", R.can_move(mb, 5, 1, 4, 3))

# 6. 塞象眼
eb = B.new_board()
place(eb, 9, 2, "B")
check("红相可飞到 (7,4)", R.can_move(eb, 9, 2, 7, 4))
place(eb, 8, 3, "P")  # 象眼
check("塞象眼后不能飞", not R.can_move(eb, 9, 2, 7, 4))
check("红相不能过河", not R.can_move(B.new_board() if False else
      (lambda b: (place(b, 4, 2, "B"), b)[1])(B.new_board()), 4, 2, 2, 4))

# 7. 炮架吃子
cb = B.new_board()
place(cb, 5, 0, "C")
place(cb, 4, 0, "P")  # 炮架
place(cb, 3, 0, "p")  # 目标（黑卒）
check("炮隔一个架可吃子", R.can_move(cb, 5, 0, 3, 0))
cb2 = B.new_board()
place(cb2, 5, 0, "C")
place(cb2, 4, 0, "P")
place(cb2, 3, 0, "P")  # 第二个架
place(cb2, 2, 0, "p")  # 目标
check("炮隔两个架不能吃", not R.can_move(cb2, 5, 0, 2, 0))
check("炮无架不能吃", not R.can_move(
    (lambda b: (place(b, 5, 0, "C"), place(b, 3, 0, "p"), b)[1])(B.new_board()),
    5, 0, 3, 0))

# 8. 将军（车）
jb = B.new_board()
place(jb, 0, 4, "k")
place(jb, 2, 4, "R")
check("车同线将军", R.in_check(jb, False))
jb2 = B.new_board()
place(jb2, 0, 4, "k")
place(jb2, 3, 4, "R")
place(jb2, 1, 4, "N")  # 红马挡住（马走日，不攻击相邻的将）
check("中间有子不将军", not R.in_check(jb2, False))

# 9. 将杀：黑将 (0,4)，红车 (0,1) 横向将军，红车 (1,5) 封逃跑点
kb = B.new_board()
place(kb, 0, 4, "k")
place(kb, 0, 1, "R")
place(kb, 1, 5, "R")
check("将杀局面 in_check", R.in_check(kb, False))
check("将杀 is_checkmate", R.is_checkmate(kb, False))
# 加一个可走到 (0,3) 垫将的黑车，应不再是将杀
place(kb, 2, 3, "r")
check("有子可解将时不是将杀", not R.is_checkmate(kb, False))

# 10. 将帅照面
fb = B.new_board()
place(fb, 0, 4, "k")
place(fb, 2, 4, "K")
check("将帅照面", R.generals_face(fb))
place(fb, 1, 4, "P")
check("中间有子不照面", not R.generals_face(fb))

# 11. 合法走法过滤（送将）
sb = B.new_board()
place(sb, 9, 4, "K")
place(sb, 0, 4, "r")  # 黑车中路将军
place(sb, 6, 2, "P")  # 红兵，走哪都解不了
check("被将军时无关棋子无合法走法", R.legal_moves(sb, 6, 2) == [])

# 12. 着法字符串往返
m = B.coords_to_move(0, 1, 2, 2)
check("坐标转着法 b0c2", m == "b0c2", m)
check("着法解析 b0c2", B.parse_move("b0c2") == (0, 1, 2, 2))

# 13. 子力价值
check("车价值高于马", P.material_value("R") > P.material_value("N"))
check("过河兵价值升高",
      P.material_value("P", 4) > P.material_value("P", 6))

print(f"\n结果：{_passed} 通过，{_failed} 失败")
sys.exit(1 if _failed else 0)
