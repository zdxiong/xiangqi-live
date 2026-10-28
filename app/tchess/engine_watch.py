"""引擎加载看门狗：检测引擎是否加载，未加载则自动重载（带节流，避免频繁触发）。"""
import time
from typing import Optional

from app.tchess.client import TchessClient
from app.tchess.models import GameState


class EngineWatchdog:
    """检测引擎加载状态；未加载且到达重试间隔时调用 TCHESS 重载接口。"""

    def __init__(self, client: TchessClient = None, retry_interval: float = 10.0):
        self.client = client or TchessClient()
        self.retry_interval = retry_interval
        self._last_retry = 0.0
        self.last_message = "尚未检测"

    def ensure(self, state: Optional[GameState] = None) -> GameState:
        """确保引擎已加载；返回（可能已更新的）状态。"""
        if state is None:
            state = self.client.get_state()
        if state.engine_loaded:
            self.last_message = "引擎已加载"
            return state

        now = time.time()
        if now - self._last_retry < self.retry_interval:
            self.last_message = "引擎未加载，等待重试间隔"
            return state

        self._last_retry = now
        try:
            r = self.client.reload_engine()
            self.last_message = "引擎重载" + ("成功" if r.get("ok") else "失败")
        except Exception as e:
            self.last_message = f"引擎重载异常: {e}"
        try:
            return self.client.get_state()
        except Exception:
            return state
