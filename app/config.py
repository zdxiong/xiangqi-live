import os


class Config:
    """应用配置。可通过同名环境变量覆盖。"""

    # TCHESS 内嵌 Web 服务地址
    TCHESS_BASE_URL = os.environ.get("TCHESS_BASE_URL", "http://127.0.0.1:8787")

    # Flask 监听
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "5000") or "5000")

    # 轮询间隔（秒），后续主循环使用
    POLL_INTERVAL = float(os.environ.get("POLL_INTERVAL", "0.5") or "0.5")

    # 目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    AUDIO_DIR = os.environ.get("AUDIO_DIR", os.path.join(BASE_DIR, "audio"))
    LOG_DIR = os.environ.get("LOG_DIR", os.path.join(BASE_DIR, "logs"))
