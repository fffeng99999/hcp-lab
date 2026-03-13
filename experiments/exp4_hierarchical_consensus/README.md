# 实验4：分层共识通信复杂度与高频负载边界

## 实验内容
- 目的：在分层共识（hierarchical）配置下，改变组数 `g`（groups），观察吞吐（TPS）、延迟、通信量估计、网络字节、以及理论通信复杂度拟合情况。
- 自变量：
  - `groups`：组数列表（默认 `32,16,8,4,2`）
  - `nodes`：总节点数（默认 `32`，要求 `nodes % g == 0`）
  - `tx`：交易总数（默认 `10000`）
  - `repeat`：每组参数重复次数（默认 `5`）
  - 其他模型参数：`message_bytes`、`base_latency_ms`、`phase_weight_inner/outer`
- 分组关系：
  - `s = nodes / g`（每组节点数）
- 共识模式：运行过程中会设置环境变量启用分层共识（见 [run_exp4.py](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp4_hierarchical_consensus/run_exp4.py#L142-L150)）：
  - `CONSENSUS_ENGINE=hierarchical`
  - `HIERARCHICAL_GROUP_COUNT=g`、`HIERARCHICAL_GROUP_SIZE=s`、`HIERARCHICAL_NODE_COUNT=nodes` 等

## 如何运行
- 入口脚本：[run_exp4_hierarchical.sh](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp4_hierarchical_consensus/run_exp4_hierarchical.sh)

```bash
bash hcp-lab/experiments/exp4_hierarchical_consensus/run_exp4_hierarchical.sh
```

可通过环境变量覆盖默认参数：

```bash
GROUP_LIST="32,16,8" NODE_COUNT=32 TX_COUNT=20000 REPEAT=3 PORT_OFFSET=4100 CHAIN_ID="hcp-exp4" \
  bash hcp-lab/experiments/exp4_hierarchical_consensus/run_exp4_hierarchical.sh
```

## 实验文件夹用途说明
- `run_exp4_hierarchical.sh`：设置默认参数并转调测试脚本。
- `test_exp4_hierarchical.sh`：构建 `hcp-loadgen`，设置实验产物目录，调用 Python 驱动脚本。
- `run_exp4.py`：实验主逻辑（对每个 g 重复运行，汇总均值/方差；输出 CSV、SVG、报告与 summary.json）。
- `report/`：实验输出目录（由脚本参数 `--out` 决定），包含：
  - `result.json`：结构化结果（每个 g 的聚合指标）
  - `exp4_summary.csv`：汇总表（含均值/标准差等）
  - `exp4_safety.csv`：安全概率模拟与理论值对照
  - `summary.json`：包含拟合指标（如 r2）与推荐 g\_star
  - `figures/*.svg`：TPS vs g、通信量 vs g、理论曲线拟合、安全曲线、Pareto 等
  - `report.md` / `report.pdf` / `report.tex`

## 中间文件与路径约定
实验会在项目根目录下写入中间产物（可由 `EXP_ARTIFACT_ROOT` 覆盖）。本实验默认：
- 实验产物根目录：`tests/exp4_hierarchical_consensus`
- 每个 g、每次 repeat 的产物目录：
  - 数据：`tests/exp4_hierarchical_consensus/g_<g>/run_<i>/data/`
  - 日志：`tests/exp4_hierarchical_consensus/g_<g>/run_<i>/logs/`
- 节点数据目录（由实验执行器再按节点数分层）：
  - `.../g_<g>/run_<i>/data/nodes_<nodes>/node<j>/`
  - `.../g_<g>/run_<i>/data/nodes_<nodes>/accounts.jsonl`
- 节点日志目录：
  - `.../g_<g>/run_<i>/logs/nodes_<nodes>/node<j>.log`
  - `.../g_<g>/run_<i>/logs/nodes_<nodes>/*gentx*` 等过程日志
- 节点二进制（启动脚本构建输出）：`tests/exp4_hierarchical_consensus/bin/hcpd`

端口说明：
- `PORT_OFFSET` 用于避免端口冲突；常用端口为：
  - CometBFT RPC：`26657 + PORT_OFFSET`
  - gRPC：`9090 + PORT_OFFSET`
