"""TCHESS 内嵌 Web 服务客户端。"""
import requests

from app.config import Config
from app.tchess.models import GameState


class TchessClient:
    """封装对 TCHESS /api/state、/api/move 的访问。"""

    def __init__(self, base_url: str = None, timeout: float = 5.0):
        self.base_url = (base_url or Config.TCHESS_BASE_URL).rstrip("/")
        self.timeout = timeout

    def get_state(self) -> GameState:
        """获取当前局面与引擎分析。"""
        resp = requests.get(self.base_url + "/api/state", timeout=self.timeout)
        resp.raise_for_status()
        return GameState.from_dict(resp.json())

    def post_move(self, move: str) -> requests.Response:
        """请求走子（观战模式下按指定着法走子）。返回原始响应，由调用方判断。"""
        return requests.post(
            self.base_url + "/api/move",
            json={"move": move},
            timeout=self.timeout,
        )

    def reload_engine(self) -> dict:
        """请求 TCHESS 重新加载默认引擎，返回响应 JSON。"""
        resp = requests.post(
            self.base_url + "/api/engine/load",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def sync_board(self) -> dict:
        """请求 TCHESS 以外部真实盘面为准同步引擎盘面。

        同步涉及截图识别，可能耗时数秒，故使用更长超时。
        """
        resp = requests.post(
            self.base_url + "/api/sync",
            timeout=max(self.timeout, 15.0),
        )
        # 不同步/失败时 TCHESS 可能返回 500，仍把 JSON 交给调用方判断
        try:
            return resp.json()
        except ValueError:
            resp.raise_for_status()
            return {"ok": False}
