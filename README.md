# xiangqi-live

基于 Python + Flask 的象棋直播联动项目。与 TCHESS 象棋辅助程序联动：获取当前局面与引擎推荐招法，分析该招的战术意图，生成中文解说与语音，并可控制走子。

## 目录结构

```
xiangqi-live/
├── app/
│   ├── api/        # Flask 路由（控制面板/健康检查）
│   ├── tchess/     # TCHESS 接口客户端（数据访问）
│   ├── engine/     # 象棋意图分析与解说
│   ├── tts/        # 语音生成（WSL CosyVoice）
│   ├── move/       # 走子控制
│   ├── core/       # 主循环编排
│   ├── config.py   # 配置
│   └── __init__.py # Flask 工厂
├── tests/
├── audio/
├── logs/
├── requirements.txt
└── run.py
```

## 快速开始

```bash
pip install -r requirements.txt
python run.py
```

启动后访问：

- 棋盘可视化页面：http://127.0.0.1:5000/（自动刷新，直观检查棋盘、行棋方与推荐招法）
- 健康检查：http://127.0.0.1:5000/health
- 状态代理（JSON）：http://127.0.0.1:5000/api/state

## 配置

可通过环境变量覆盖默认值，例如：

- `TCHESS_BASE_URL`（默认 http://127.0.0.1:8787）
- `HOST` / `PORT`（Flask 监听，默认 127.0.0.1:5000）
