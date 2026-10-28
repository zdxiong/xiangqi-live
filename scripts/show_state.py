"""独立调试脚本：打印当前 TCHESS 局面、棋盘与推荐招法。

运行（在项目根目录）：
    python -m scripts.show_state
"""
from app.tchess.client import TchessClient


def main():
    client = TchessClient()
    s = client.get_state()

    print("=" * 50)
    print(f"引擎: {s.engine_name} ({'已加载' if s.engine_loaded else '未加载'})")
    print(f"FEN: {s.fen}")
    print(f"行棋方: {s.side_to_move}  翻转: {s.is_reverse}  分析模式: {s.analysis_mode}  思考中: {s.thinking}")
    print("-" * 50)
    print("棋盘:")
    for row in s.board:
        print("  " + " ".join(c if c != " " else "·" for c in row))
    print("-" * 50)

    a = s.analysis
    print(f"推荐主线（{a.count} 条）:")
    for ln in a.lines:
        mate = f"  mate={ln.mate}" if ln.mate else ""
        print(f"  pv={ln.pv} depth={ln.depth} score={ln.score}{mate} best={ln.best_move}")
        if ln.move_cn:
            print(f"      {ln.move_cn}")
    if a.best:
        print("-" * 50)
        print(f"最佳: {a.best.best_move}  {a.best.move_cn or ''}")
    print("=" * 50)


if __name__ == "__main__":
    main()
