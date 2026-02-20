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
- 两阶段搜索：先粗筛，再大样本精算 Top 策略。
- 结果保存为 JSON + CSV。

## 运行

```bash
python main.py --G 14 --mode discard --N 300000 --search
```

### 常用参数

- `--G`: 目标阈值（如 14/16/18/20/22）
- `--N`: 单策略评估模拟次数（默认 200000）
- `--a1 --a2 --a3 --a4`: 四阶段分数门槛
- `--gate2-ge3`: 开启前两槽逻辑门槛
- `--probabilities`: 26 维概率，逗号分隔（会自动归一化）
- `--search`: 启用两阶段穷举
- `--max-threshold`: 搜索上限（默认 20）
- `--coarse-n/--fine-n`: 粗筛与精算样本量
- `--top-k/--top-n`: 粗筛保留 K，最终输出前 N
- `--compare-example`: 一键对比示例策略
- `--similar-threshold-pct`: “差不多”判定阈值（默认 5%）

### 示例

1) 单策略评估（仅丢弃）

```bash
python main.py --G 16 --mode discard --a1 3 --a2 6 --a3 8 --a4 11 --N 250000
```

2) 对比示例策略

```bash
python main.py --G 16 --mode discard --N 250000 --compare-example
```

3) 搜索最优策略（两阶段）

```bash
python main.py --G 14 --mode mixed --restart-action auto --search \
  --max-threshold 15 --coarse-n 15000 --fine-n 150000 --top-k 40 --top-n 10
```

## 文件结构

- `strategy.py`: 策略与状态定义
- `simulator.py`: 单次/批量 Monte Carlo 模拟
- `search.py`: 单调门槛穷举 + 两阶段搜索
- `main.py`: CLI 入口、输出与对比结论

## 依赖

- Python 3.9+
- 无第三方依赖（纯 Python 标准库即可运行）
- 可选安装 `numpy` 后自行扩展向量化版本
