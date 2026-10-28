"""Flask 路由：棋盘可视化页面、健康检查、TCHESS 状态代理与走子代理。"""
from dataclasses import asdict

from flask import Blueprint, jsonify, render_template, request

from app.tchess.client import TchessClient
from app.tchess.models import Analysis
from app.tchess.engine_watch import EngineWatchdog

bp = Blueprint("api", __name__)

# 引擎看门狗单例（保持节流状态）
watchdog = EngineWatchdog()


@bp.get("/")
def index():
    """棋盘可视化页面。"""
    return render_template("index.html")


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/api/state")
def api_state():
    """代理 TCHESS 当前局面与分析，供页面轮询。

    己方视角：只在轮到己方走子时保留推荐；对方回合（含己方走完等待对方）
    推荐一律清空，不显示对方的推荐。
    """
    try:
        state = TchessClient().get_state()
        state = watchdog.ensure(state)  # 引擎未加载则自动重载（节流）
        if not state.my_turn:
            state.analysis = Analysis()
        data = asdict(state)
        data["engineWatch"] = watchdog.last_message
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"无法连接 TCHESS: {e}"}), 502


@bp.post("/api/engine/reload")
def api_engine_reload():
    """手动触发引擎重载。"""
    try:
        return jsonify(TchessClient().reload_engine())
    except Exception as e:
        return jsonify({"ok": False, "error": f"无法连接 TCHESS: {e}"}), 502


@bp.post("/api/sync")
def api_sync():
    """代理盘面同步：请求 TCHESS 以外部真实盘面为准同步引擎盘面。"""
    try:
        result = TchessClient().sync_board()
        code = 200 if result.get("ok") else 500
        return jsonify(result), code
    except Exception as e:
        return jsonify({"ok": False, "error": f"无法连接 TCHESS: {e}"}), 502


@bp.post("/api/play")
def api_play():
    """代理走子：把指定着法转发给 TCHESS /api/move。

    仅在轮到己方走子时放行；己方走完后到对方出招之前禁止再次出子。
    """
    data = request.get_json(silent=True) or {}
    move = (data.get("move") or "").strip()
    if not move:
        return jsonify({"ok": False, "error": "缺少 move 参数"}), 400
    try:
        state = TchessClient().get_state()
        if not state.my_turn:
            return jsonify({"ok": False, "error": "未轮到己方走子，等待对方走子"}), 403
        resp = TchessClient().post_move(move)
        try:
            return jsonify(resp.json()), resp.status_code
        except ValueError:
            return jsonify({"ok": False, "error": "TCHESS 响应异常", "status": resp.status_code}), resp.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": f"无法连接 TCHESS: {e}"}), 502
