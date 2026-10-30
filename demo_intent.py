"""意图分析演示：在初始棋盘上跑若干合法着法，输出结构化意图。"""
from app.engine.board import initial_board
from app.engine.intents import analyze_intent

ib = initial_board()
moves = ["h2g2", "h0g2", "b0c2", "i0i1", "g3g4"]

with open("demo_output.txt", "w", encoding="utf-8") as f:
    for m in moves:
        r = analyze_intent(ib, m)
        f.write(f"{m} -> [{r.category_cn}] {r.primary_cn}\n")
        for reason in r.reasons:
            f.write(f"    - {reason}\n")
print("Written to demo_output.txt")
