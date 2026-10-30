# PROJECT_LEDGER.md

> 由 AI 自动维护；项目结构/命令/依赖变化时顺手更新对应字段，保留用户补充的原文与备注。

## 基本信息
- 项目名：xiangqi-live（抖音象棋直播联动助手）
- 项目类型：本地 Web 服务（Flask 单体应用），作为外部 TCHESS 象棋辅助程序的代理与增强层
- 主要语言：Python
- 定位：与 TCHESS（内嵌 Web 服务，127.0.0.1:8787）联动——获取当前局面与引擎推荐招法，分析战术意图，生成中文解说与语音，并可控制走子

## 技术栈
- 语言及版本：Python 3.13.16（实测）
- 框架：Flask（应用工厂 + Blueprint），原生 Jinja 模板
- 核心库：requests（HTTP 调用 TCHESS）；前端为原生 JS + 内联 SVG，无前端构建链
- 数据库：无
- 棋类引擎：皮卡鱼 Pikafish 由 TCHESS 侧加载（本仓库 `engines/Pikafish/` 目前为空目录）

## 目录结构
- 关键目录 → 职责：
  - `run.py` → 入口，create_app() 后按 config 监听
  - `app/__init__.py` → Flask 应用工厂，注册 api 蓝图
  - `app/config.py` → 配置类，环境变量覆盖
  - `app/api/routes.py` → 全部 HTTP 路由（页面、状态代理、走子、引擎重载、盘面同步）
  - `app/tchess/` → TCHESS 接口层：`client.py`（HTTP 客户端）、`models.py`（GameState/Analysis/MoveLine dataclass）、`engine_watch.py`（引擎加载看门狗，10s 节流自动重载）
  - `app/engine/` → 象棋内核：
    - `board.py`（棋盘/着法解析/FEN）、`pieces.py`（棋子常量/中文名/价值）、`rules.py`（走法规则、将军将杀判断）
    - `snapshot.py`（**盘面客观事实快照层**：take_snapshot 一次性算清被将军/全部合法走法/有根无根/被抓/真实威胁，compare 吃子对比，move_verb 中文叫法）
    - `intents.py`（全招法意图分析：走前/走后各取一次快照，再基于快照按优先级判断，6 大类 30 标签）
  - `app/move/` → 走子控制：**仅有 docstring，未实现**
  - `app/tts/` → 语音生成（设计为 WSL CosyVoice）：**仅有 docstring，未实现**
  - `app/core/` → 主循环编排：**仅有 docstring，未实现**
  - `app/templates/index.html` → 单页控制台（SVG 棋盘，1.5s 轮询 /api/state）
  - `app/static/audio/` → 音频输出目录
  - `scripts/` → `show_state.py`（局面调试）、`verify_rules.py`（规则层 33 项校验）、`verify_intent.py`（意图层 17 项校验，可直接运行）
  - `INTENT_DESIGN.md` → 意图体系设计文档（分类全集 / 事实层 / 优先级链 / 输出结构 / 页面方案）
  - `demo_intent.py` → 意图引擎离线演示，输出 `demo_output.txt`
  - `audio/`、`data/`、`tests/`、`engines/Pikafish/` → 目前均为空目录
  - `logs/` → 调试截图、wav、进程记录（.gitignore 忽略，不入库）

## 命令
- 构建：无（纯 Python，无构建步骤）
- 安装依赖：`pip install -r requirements.txt`
- 启动：`python run.py`（默认 127.0.0.1:5000）
- 测试：`python scripts/verify_rules.py`（规则层 33 项）、`python scripts/verify_intent.py`（意图层 17 项），均无 pytest 依赖，退出码反映成败；`tests/` 目录为空
- 调试：`python -m scripts.show_state`；意图演示 `python demo_intent.py`
- lint：无配置

## 核心依赖
- Flask（>=3.0）→ Web 服务、模板、路由
- requests（>=2.31）→ 调用 TCHESS HTTP 接口

## 规范与约定
- 代码内 docstring 为中文，模块分层清晰（数据访问 tchess / 领域 engine / 传输 api / 编排 core）
- 数据模型统一使用 dataclass，`from_dict` 负责 TCHESS 驼峰字段 → Python 字段映射
- 棋盘坐标契约（隐藏契约，改动前必须实测，已用真实 /api/state 交叉验证）：
  - `board[y][x]`：y=0 黑方底线 … y=9 红方底线；x=0…8
  - 着法字符串 4 字符：file 字母 a-i = x；rank 数字 0-9 从**红方底线**起算，即 `y=9-rank`、`rank=9-y`（parse_move / coords_to_move 已按此实现，禁止回退为 rank 直接当 y）
  - 棋子字符：红方大写 K帅 A仕 B相 N马 R车 C炮 P兵；黑方小写 k将 a士 b象 n马 r车 c炮 p卒；空格为 EMPTY
  - 实测锚点：d7d0 = 黑炮 (2,3) 吃红仕 (9,3)；a0a1 = 红车 (9,0)→(8,0)；h2e2 = 红炮 (7,7)→(7,4) 当头炮
- 规则层对应 Java 端 XiangqiUtils.canGo/isJiang：can_move 为伪合法（不考虑送将/照面），legal_moves 过滤走完后己方被将的走法

## 环境要求
- 运行时版本：Python 3.13（Windows 本地运行，PowerShell）
- 外部服务：
  - TCHESS 程序必须运行并提供 `http://127.0.0.1:8787`（接口：GET /api/state、POST /api/move、POST /api/engine/load、POST /api/sync）
  - TTS 规划走 WSL 中的 CosyVoice（尚未实现）
- 环境变量 / 配置项：`TCHESS_BASE_URL`（默认 http://127.0.0.1:8787）、`HOST`（127.0.0.1）、`PORT`（5000）、`POLL_INTERVAL`（0.5s）、`AUDIO_DIR`、`LOG_DIR`
- 当前实测端口：5000（Flask，PID 51104，2026-10-30 重启，单实例，服务工作区新代码）、8787（TCHESS）均在监听

## 已知事项
- 架构说明：
  - 回合安全设计：/api/state 在非己方回合清空 analysis（不显示对方推荐）；/api/play 仅 my_turn 时放行，防重复出子
  - 看门狗单例挂在 routes 模块，保持节流状态
- 意图引擎重构（2026-10-29 ~ 30 完成，旧 rules.analyze_intent 已删除，缺陷全部解决）：
  - 新引擎 `app/engine/intents.py`：`IntentResult` dataclass（to_dict 输出驼峰字段，兼容旧字段名并新增 reasons/phaseCn/categoryCn/categoryCode/openingCn）
  - 6 大类 + invalid，共 30 个 primaryCode：
    - mate 杀攻：checkmate、stalemate、double_check、discovered_check、royal_cannon、double_cannon、check
    - defense 防御：capture_checker、king_evade、block_check
    - capture 吃兑：check_capture、winning_exchange、trade、sacrifice、capture
    - threat 威胁：threat_mate、fork、hunt、pin、press
    - position 位置：cross_river、center、river_press、key_point、blockade
    - development 调运：opening、develop、setup、flee、protect、redeploy
  - 客观事实层：detect_phase、can_reach（虚拟敌子替换）、is_protected、attack_targets、real_threat（模拟吃子判断是否被吃回/交换是否划算，过滤"隔山瞄"假攻击）、find_pins、has_mate_in_one（二步深度模拟）、screen_piece、protecting_target、blockade_target
  - 优先级链：非法着法 → 将死/困毙 → 应将 → 将军（双将/抽吃/闪将/马后炮/重炮/普通）→ 吃子 → 开局谱 → 叫杀 → 捉双/捉子 → 牵制 → 逃子 → 压马 → 位置类 → 出动/上士飞象 → 调运兜底（逃子优先于压马：移动子自身被真实威胁时，退路上对有根马的瞄着只是附带）
  - 后端 `routes.py`：/api/state 在己方回合基于 board + best_move 计算 intent 注入，对方回合为 null
  - 前端 `index.html`：新增"战术意图"卡片（大类彩色标签、阶段、开局徽章、主意图、详情、着法/吃子元信息、reasons 客观依据）与"意图历史"卡片（按 fen+move 去重，保留最近 10 条）
  - 验证：verify_intent 17/17、verify_rules 33/33 全通过；浏览器实测两类卡片渲染正确
- 快照两阶段架构（2026-10-30 按用户规则重构，事实与判断分离）：
  - 走前 take_snapshot：己方是否被将军、双方全部合法走法（行棋空间）、双方有根/无根、双方被抓棋子
  - 走后 take_snapshot：敌方是否被将军、同上全部字段；compare 给出相对走前是否少子及被吃棋子（位置/名称/归属）
  - **将帅（王）不参与有根/无根归类**：王不能被吃、无保护概念，跳过 rooted/unrooted 列表（实测校准，否则会把王误算成无根子）
  - **"被抓"=真实捉（real_threat）**：敌子下一步可白吃或净赚才计入；纯几何瞄着有根子不算被抓，只留在单子 PieceFact.attacked_by。交换判定用 `atk_val >= victim_val`：等价交换（如同价炮吃炮、有保护者会吃回）对方占不到便宜，也不算真实威胁（曾因严格 > 把等价交换误判成逃子）。SideFact 已去掉冗余 real_threatened，前端网格为将军/走法/无根/被抓 4 列
  - **"保子"只针对走前确实需要保护的子**：目标走前被攻击且无根/受真实威胁，走子后才补根才算 protect；若目标走前已有根（如车平到有根炮同一线），不是保子，按亮车 develop 处理
  - 分类器只消费快照字段，不再零散临时计算；前端以网格展示走前→走后双方 4 项事实
  - 中文叫法 move_verb（方向以行棋方自身为准，红 dy<0/黑 dy>0 为前进）：
    兵卒 进/拱、平；炮 进/退/平、吃子=飞炮吃子；马 进/回；车 进/退/平；
    象 飞/回；士 补/落；将帅 出将/进将/落将
- 已知局限：单步意图只看可严格计算的客观事实，无法完全理解皮卡鱼多步深度战术（如引擎推荐的 d7d0 单步判"弃子"，但全局可能是有利攻势），故以 reasons 让用户逐条核对，不做主观臆测
- 历史经验（workspace experience）：
  - 对接 UCI/皮卡鱼须先实测坐标字段映射，曾因 rank 方向搞反导致约 9 成意图错误；主观软规则宁缺毋滥，安静步落"调运"兜底
  - 重启本地 Flask 后须核对端口 PID 与启动时间，防旧进程残留服务旧代码
- 参考项目：`C:\Users\xiongzhendong\work\projects\public-Xiangqi-master`（TCHESS Java 源码 + tactic_commentator.py，提供攻击/有根/牵制/开局谱等可复用战术体系）
- Git：main 分支，2 个提交（初始化、web界面调整）；本次重构大量改动尚未提交
- 负责人 / 备注：用户本人（owner）
