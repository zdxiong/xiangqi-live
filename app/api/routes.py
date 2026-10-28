"""Flask 路由：棋盘可视化页面、健康检查、TCHESS 状态代理与走子代理。"""
from dataclasses import asdict

from flask import Blueprint, jsonify, render_template, request

from app.tchess.client import TchessClient

bp = Blueprint("api", __name__)


@bp.get("/")
def index():
    """棋盘可视化页面。"""
    return render_template("index.html")


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/api/state")
def api_state():
    """代理 TCHESS 当前局面与分析，供页面轮询。"""
    try:
        state = TchessClient().get_state()
        return jsonify(asdict(state))
    except Exception as e:
        return jsonify({"error": f"无法连接 TCHESS: {e}"}), 502


@bp.post("/api/play")
def api_play():
    """代理走子：把指定着法转发给 TCHESS /api/move。"""
    data = request.get_json(silent=True) or {}
    move = (data.get("move") or "").strip()
    if not move:
        return jsonify({"ok": False, "error": "缺少 move 参数"}), 400
    try:
        resp = TchessClient().post_move(move)
        try:
            return jsonify(resp.json()), resp.status_code
        except ValueError:
            return jsonify({"ok": False, "error": "TCHESS 响应异常", "status": resp.status_code}), resp.status_code
    except Exception as e:
        return jsonify({"ok": False, "error": f"无法连接 TCHESS: {e}"}), 502
