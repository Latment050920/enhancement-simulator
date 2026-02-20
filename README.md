# enhancement-simulator

用于模拟我的世界装备强化系统，并对门槛策略进行 Monte Carlo 评估与两阶段穷举搜索。

## 功能

- 支持 6 槽强化、26 属性（默认均匀，可自定义概率）。
- 仅 4 种攻击属性计分，规则：
  - `S = max(sum_melee, sum_ranged) + sum_physical + sum_true`
- 成本模型输出：
  - 期望服务器币（含强化费/清除费/钻石折价/龙泪折价）
  - 期望钻石消耗
  - 期望龙泪消耗
- 策略可配置：`a1,a2,a3,a4` + 可选逻辑门槛（前两槽至少出现一次攻击且数值 >= 3）。
- 两种模式：
  - `discard`: 仅允许丢弃重做
  - `mixed`: 允许丢弃+洗点重置（`--restart-action auto|discard|reset`）
  - reset 默认保留同一件装备的 5/6 槽解锁状态（可用 `--no-persist-slot-unlocks-on-reset` 关闭）
- 两阶段搜索：先粗筛，再大样本精算 Top 策略。
- 运行进度反馈：`--progress` 开启后显示 Monte Carlo 和 Search 进度（若有 `rich` 优先使用 rich progress）。
- 每次运行自动生成报告目录：`outputs/YYYYMMDD_HHMMSS/`
  - `summary.json`
  - `results.csv`
  - `report.html`（离线可打开）

## 运行

```bash
python main.py --G 14 --mode discard --N 300000 --search --progress
```

### 常用参数

- `--G`: 目标阈值（支持单值或逗号多值，如 `14,16,18`）
- `--N`: 单策略评估模拟次数（默认 200000）
- `--a1 --a2 --a3 --a4`: 四阶段分数门槛
- `--gate2-ge3`: 开启前两槽逻辑门槛
- `--probabilities`: 26 维概率，逗号分隔（会自动归一化）
- `--probabilities-envs`: 多概率环境（用 `;` 分隔多个 26 维向量）
- `--search`: 启用两阶段穷举
- `--max-threshold`: 搜索上限（默认 20）
- `--coarse-n/--fine-n`: 粗筛与精算样本量
- `--top-k/--top-n`: 粗筛保留 K，最终输出前 N
- `--compare-example`: 一键对比示例策略
- `--similar-threshold-pct`: “差不多”判定阈值（默认 5%）
- `--persist-slot-unlocks-on-reset / --no-persist-slot-unlocks-on-reset`: 控制 reset 后是否保留 5/6 槽解锁（默认保留）
- `--progress`: 开启运行进度
- `--progress-every`: 进度刷新批大小（默认 5000）

### 示例

1) 单策略评估（仅丢弃）

```bash
python main.py --G 16 --mode discard --a1 3 --a2 6 --a3 8 --a4 11 --N 250000 --progress
```

2) 对比示例策略

```bash
python main.py --G 16 --mode discard --N 250000 --compare-example --progress
```

3) 搜索最优策略（两阶段）

```bash
python main.py --G 14 --mode mixed --restart-action auto --search \
  --max-threshold 15 --coarse-n 15000 --fine-n 150000 --top-k 40 --top-n 10 --progress
```

4) 多 G 分组运行

```bash
python main.py --G 14,16,18 --mode discard --N 100000 --progress
```

## 报告查看

运行结束后终端会打印：
- `Report folder: outputs/YYYYMMDD_HHMMSS`
- `Open in browser: outputs/YYYYMMDD_HHMMSS/report.html`

直接用浏览器打开该 `report.html` 即可离线查看指标卡片、策略对比柱图、成本分解和误差信息。

## 文件结构

- `strategy.py`: 策略与状态定义
- `simulator.py`: 单次/批量 Monte Carlo 模拟
- `search.py`: 单调门槛穷举 + 两阶段搜索
- `reporter.py`: summary/csv/html 报告生成
- `main.py`: CLI 入口、进度显示、输出与对比结论

## 依赖

- Python 3.9+
- 无第三方依赖（纯 Python 标准库即可运行）
- 可选：`rich`（更好看的进度条）
