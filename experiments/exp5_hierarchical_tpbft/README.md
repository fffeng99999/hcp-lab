# 实验5：分层 TPBFT（Hierarchical TPBFT）

## 实验内容
- 目的：在分层 TPBFT（`hierarchical-tpbft`）下，改变组数 `g` 与阈值签名算法（如 `bls`/`ed25519`），观察 TPS/延迟与“签名瓶颈迁移”的指标（签名生成/验签/聚合耗时、消息数、通信字节、CPU、网络字节等）。
- 自变量：
  - `groups`：组数列表（默认 `32,16,8,4,2`）
  - `sig_algos`：签名算法列表（默认 `bls,ed25519`）
  - `nodes`：总节点数（默认 `32`，要求 `nodes % g == 0`）
  - `tx`：交易总数（默认 `100`）
  - `repeat`：每组参数重复次数（默认 `5`）
  - 其他参数：消息大小、阶段权重、签名耗时模型、批量验签开关/加速比/并行度、batch_size 等
- 分组关系：
  - `s = nodes / g`（每组节点数）
- 共识模式：运行过程中会设置环境变量启用分层 TPBFT（见 [run_exp5.py](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp5_hierarchical_tpbft/run_exp5.py#L162-L199)）：
  - `CONSENSUS_ENGINE=hierarchical-tpbft`
  - `HIERARCHICAL_GROUP_COUNT=g`、`HIERARCHICAL_GROUP_SIZE=s`、`HIERARCHICAL_SIG_ALGO=<algo>` 等

## 如何运行
- 入口脚本：[run_exp5_hierarchical_tpbft.sh](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp5_hierarchical_tpbft/run_exp5_hierarchical_tpbft.sh)

```bash
bash hcp-lab/experiments/exp5_hierarchical_tpbft/run_exp5_hierarchical_tpbft.sh
```

可通过环境变量覆盖默认参数：

```bash
GROUP_LIST="32,16,8" SIG_ALGO_LIST="bls,ed25519" NODE_COUNT=32 TX_COUNT=2000 REPEAT=3 PORT_OFFSET=5100 CHAIN_ID="hcp-exp5" \
  bash hcp-lab/experiments/exp5_hierarchical_tpbft/run_exp5_hierarchical_tpbft.sh
```

也可以直接运行 Python 并覆写更细粒度参数（例如 batch verify、签名耗时模型等），见 [run_exp5.py](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp5_hierarchical_tpbft/run_exp5.py) 的参数列表。

## 实验文件夹用途说明
- `run_exp5_hierarchical_tpbft.sh`：设置默认参数并转调测试脚本。
- `test_exp5_hierarchical_tpbft.sh`：构建 `hcp-loadgen`，设置实验产物目录，调用 Python 驱动脚本。
- `run_exp5.py`：实验主逻辑（按 algo×g×repeat 运行，汇总均值/方差；输出 CSV、SVG、报告与 summary.json）。
- `report/`：实验输出目录（由脚本参数 `--out` 决定），包含：
  - `result.json`：结构化结果
  - `exp5_summary.csv`：汇总表（含签名/通信/资源等指标）
  - `summary.json`：本次实验的配置摘要
  - `figures/*.svg`：tps/messages/sig_time/net_bytes/cpu vs g（按 algo 分图）
  - `report.md` / `report.pdf` / `report.tex`

## 中间文件与路径约定
实验会在项目根目录下写入中间产物（可由 `EXP_ARTIFACT_ROOT` 覆盖）。本实验默认：
- 实验产物根目录：`tests/exp5_hierarchical_tpbft`
- 每个 algo、每个 g、每次 repeat 的产物目录：
  - 数据：`tests/exp5_hierarchical_tpbft/algo_<algo>/g_<g>/run_<i>/data/`
  - 日志：`tests/exp5_hierarchical_tpbft/algo_<algo>/g_<g>/run_<i>/logs/`
- 节点数据目录（由实验执行器再按节点数分层）：
  - `.../algo_<algo>/g_<g>/run_<i>/data/nodes_<nodes>/node<j>/`
  - `.../algo_<algo>/g_<g>/run_<i>/data/nodes_<nodes>/accounts.jsonl`
- 节点日志目录：
  - `.../algo_<algo>/g_<g>/run_<i>/logs/nodes_<nodes>/node<j>.log`
  - `.../algo_<algo>/g_<g>/run_<i>/logs/nodes_<nodes>/*gentx*` 等过程日志
- 节点二进制（启动脚本构建输出）：`tests/exp5_hierarchical_tpbft/bin/hcpd`

端口说明：
- `PORT_OFFSET` 用于避免端口冲突；常用端口为：
  - CometBFT RPC：`26657 + PORT_OFFSET`
  - gRPC：`9090 + PORT_OFFSET`
