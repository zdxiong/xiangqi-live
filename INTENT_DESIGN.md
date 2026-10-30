# 象棋意图分析体系 · 设计文档

## 1. 目标

1. 页面直接展示当前推荐着法的**意图标签 + 客观依据 + 历史记录**，方便人工核对对错。
2. 意图体系**覆盖象棋全部招法**：任何合法走法都能落到一个有客观依据的标签；安静步统一兜底为"调运"，不输出无依据的花哨判断。
3. 所有软规则（捉、牵制、逃、叫杀）均基于可严格计算的棋盘事实，禁止"理论上可能"的静态臆测。

## 2. 坐标契约（首要修复项）

实测确认（真实着法 d7d0、a0a1 与中文着法交叉验证）：

- TCHESS 着法字符串遵循 UCI 编号：`rank` 从**红方底线**起编号，与棋盘视觉行方向相反。
- 映射：`y = 9 - rank`，`rank = 9 - y`；`x = file`（列字母 a-i 直接对应 0-8）。
- 旧 `board.py` 把 rank 直接当 y，导致每步着法解析到错误位置（黑炮被解析到空点），必须修复 `parse_move` / `coords_to_move`。
- 棋盘：`board[y][x]`，y=0 黑方底线 … y=9 红方底线；红方大写、黑方小写。

## 3. 客观事实层（facts，全部可复算）

| 事实 | 计算方式 |
| --- | --- |
| 合法性 | `can_move` 校验；非法着法直接标"非法着法"，不硬算 |
| 吃子 | 落点非空且为敌子，记录被吃子与价值 |
| 将军状态 | 走前/走后双方 `in_check`（含将帅照面） |
| 将军来源 | `attackers(对方王位)`，数量用于双将/闪将判定 |
| 移动子攻击面 | 走后棋盘上移动子可吃的敌子列表（一步深度） |
| 有根/保护 | 目标子是否被同方其他子保护（reach 线路） |
| 叫杀 | 走后不将军，但模拟己方全部下一步走法，存在将死即叫杀（二步深度） |
| 牵制 pin | 对方子在直线上挡住我方车/炮与其后方将帅/高价值子 |
| 逃子 | 走前移动子被攻击，走后落点不被攻击 |
| 位置 | 落点 x=4（中路）、兵卒过河、进入对方半场、肋道(x=3/5) |
| 阶段 | 棋子总数 + FEN fullmove：opening / middle / endgame |

## 4. 意图分类全集（6 大类 30 标签）

### 4.1 杀攻类 mate
| code | 标签 | 客观条件 |
| --- | --- | --- |
| checkmate | 将死 | 对方被将军且无合法走法 |
| stalemate | 困毙 | 对方未被将军但无合法走法 |
| double_check | 双将 | 将军来源 ≥2 |
| discovered_check | 闪将 | 将军来源不含移动子（让开露后子） |
| royal_cannon | 马后炮 | 炮将军且炮架为对方马 |
| double_cannon | 重炮 | 炮将军且炮架为对方炮 |
| check | 将军 | 走后对方被将军（一般情况） |

### 4.2 防御类 defense（走前己方被将军，首要意图为应将）
| code | 标签 | 客观条件 |
| --- | --- | --- |
| capture_checker | 吃子解将 | 吃掉将军来源子 |
| king_evade | 躲将 | 移动将帅且走后不被将 |
| block_check | 垫将 | 非吃子非动帅，挡在将军线路 |

### 4.3 吃兑类 capture（落点为敌子）
| code | 标签 | 客观条件 |
| --- | --- | --- |
| check_capture | 将军抽吃 | 将军且移动子另攻击无根子 |
| winning_exchange | 换子有利 | 被吃子价值显著高于我方子 |
| trade | 兑子 | 价值相当且落点被对方攻击 |
| sacrifice | 弃子 | 落点被高价值对方子攻击且我方子价值更高 |
| capture | 吃子 | 一般吃子，标签带被吃子名 |

### 4.4 威胁类 threat（不吃子、不将军但产生新攻击关系）
| code | 标签 | 客观条件 |
| --- | --- | --- |
| threat_mate | 叫杀 | 二步模拟存在将死 |
| fork | 捉双 | 移动子可同时吃 ≥2 个无根子 |
| hunt | 捉子 | 可吃 1 个无根子，带目标名 |
| pin | 牵制 | 新形成 pin 关系 |
| press | 压马/压制 | 车攻击对方有根马等 |

### 4.5 位置类 position
| code | 标签 | 客观条件 |
| --- | --- | --- |
| cross_river | 过河 | 兵卒过河 |
| center | 控制中路 | 落点 x=4 |
| river_press | 压制河界 | 进入对方半场 |
| key_point | 抢占要点 | 车占肋道等要点 |
| blockade | 封锁 | 线路客观封堵对方子活动 |

### 4.6 调运布局类 development
| code | 标签 | 客观条件 |
| --- | --- | --- |
| opening | 开局名 | 开局阶段命中开局谱（当头炮/仙人指路/飞相局/起马局/左炮巡河/过宫炮/仕角炮） |
| develop | 出动大子 | 开局阶段车马炮移动 |
| setup | 上士飞象 | 士/象移动，巩固阵型 |
| flee | 逃子 | 被攻子转移到安全点 |
| protect | 保子 | 走后掩护己方另一被攻子 |
| redeploy | 调运 | 兜底：以上客观事实均不命中的安静步 |

## 5. 判定优先级链（显式 if/elif，禁止无条件兜底遮蔽后续分支）

1. 终局：checkmate / stalemate
2. 应将（走前己方被将）：capture_checker → king_evade → block_check
3. 将军：double_check → check_capture → discovered_check → royal_cannon/double_cannon → check
4. 吃子：sacrifice → trade → winning_exchange → capture
5. threat_mate（叫杀）
6. fork / hunt（捉双/捉子）
7. pin（牵制）
8. flee（逃子）/ protect（保子）
9. 位置：cross_river → center → river_press → key_point → blockade
10. 开局：opening → develop → setup
11. redeploy（调运兜底，保证 100% 覆盖）

## 6. 输出结构（兼容旧字段并增强）

```json
{
  "move": "d7d0",
  "valid": true,
  "phase": "opening",
  "pieceCn": "炮",
  "fromPos": "d7",
  "toPos": "d0",
  "capturedCn": "仕",
  "categoryCode": "capture",
  "categoryCn": "吃兑",
  "primaryCode": "capture",
  "primaryCn": "吃子（吃仕）",
  "primaryDetail": "黑炮吃掉红仕，获得子力",
  "openingCn": "",
  "tagsCn": ["吃子"],
  "reasons": ["起点为黑炮", "终点为红仕", "吃子价值200", "落点未被对方攻击"],
  "pvPreview": ["d0f0", "f0c0"],
  "summary": "黑炮吃掉红仕，获得子力"
}
```

`reasons` 为本次新增：每条结论都可在棋盘上人工复核，是判断对错的核心。

## 7. 页面展示方案

- 新增"战术意图"卡片（引擎推荐下方）：大类彩色标签 + 阶段标签 + 主意图（大字）+ 客观依据列表 + 开局名。
- 新增"意图历史"卡片：前端按 best_move 变化追加，保留最近 10 条（着法 + 标签 + 阶段），刷新页面清空。
- 无推荐/对方回合：空状态文案，不显示意图。
- 大类配色：杀攻红、防御蓝、吃兑橙、威胁紫灰、位置青、调运灰。

## 8. 验证方案

- `scripts/verify_intent.py`：
  1. 初始棋盘全部合法走法逐一分析：无异常、100% 有标签、reasons 非空；
  2. 典型局面：将军/将死/双将/闪将/吃子/兑子/弃子/逃子/捉双/叫杀/牵制/过河/开局名；
  3. 输出意图分布统计。
- `scripts/verify_rules.py`：坐标契约修复后更新断言，保持全部通过。
- 重启 Flask（核对端口 PID 杀旧启新），端到端验证页面与接口真实输出。

## 9. 改动文件清单

| 文件 | 改动 |
| --- | --- |
| `app/engine/board.py` | 修复 parse_move/coords_to_move 坐标契约（rank=9-y） |
| `app/engine/intents.py` | 新建：事实层 + 分类器 + IntentResult |
| `app/engine/rules.py` | 移除有缺陷的旧 analyze_intent，保留规则函数 |
| `app/api/routes.py` | /api/state 注入结构化 intent |
| `app/templates/index.html` | 意图卡片 + 历史卡片 |
| `scripts/verify_intent.py` | 新建：覆盖度与典型局面验证 |
| `demo_intent.py` | 适配新接口 |
| `.ai/PROJECT_LEDGER.md` | 回填变更 |
