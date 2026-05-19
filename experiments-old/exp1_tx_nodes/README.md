# 实验1：交易量 × 节点规模

## 实验内容
- 目的：评估在不同节点规模下，固定交易量的完成耗时、TPS、延迟（含 P99）、资源占用等指标变化。
- 自变量：
  - `nodes`：节点数（默认 `4,8,16`）
  - `tx`：交易总数（默认 `100`）
- 因变量（采集输出）：`tps`、`avg_confirm_time_ms`、`p50/p95/p99`、`cpu_percent`、`net_mbps`、RocksDB 写入耗时等。

## 如何运行
- 入口脚本：[run_exp1_tx_nodes.sh](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp1_tx_nodes/run_exp1_tx_nodes.sh)

```bash
bash hcp-lab/experiments/exp1_tx_nodes/run_exp1_tx_nodes.sh
```

可通过环境变量覆盖默认参数：

```bash
NODES_LIST="4,8,16,32" TX_LIST="100,1000" PORT_OFFSET=1100 CHAIN_ID="hcp-exp1" \
  bash hcp-lab/experiments/exp1_tx_nodes/run_exp1_tx_nodes.sh
```

## 实验文件夹用途说明
- `run_exp1_tx_nodes.sh`：设置默认参数并转调测试脚本。
- `test_exp1_tx_nodes.sh`：构建 `hcp-loadgen`，设置实验产物目录，启动实验执行器（Python）。
- `run_exp1.py`：实验编排逻辑（矩阵展开、启动节点、调用负载、采集指标、生成报告）。
- `report/`：实验输出目录（由脚本参数 `--out` 决定），包含：
  - `result.json`：结构化实验结果
  - `report.md` / `report.pdf` / `report.tex`：报告（PDF 若缺 LaTeX 引擎可能为 None）

## 中间文件与路径约定
实验会在项目根目录下写入中间产物（可由 `EXP_ARTIFACT_ROOT` 覆盖）。本实验默认：
- 实验产物根目录：`tests/exp1_tx_nodes`
- 节点数据目录（每个实验点独立一套）：`tests/exp1_tx_nodes/data/nodes_<nodes>/`
  - 单节点 home：`tests/exp1_tx_nodes/data/nodes_<nodes>/node<i>/`（例如 `node1`）
  - 负载账户文件：`tests/exp1_tx_nodes/data/nodes_<nodes>/accounts.jsonl`
  - 节点地址：`tests/exp1_tx_nodes/data/nodes_<nodes>/node<i>/address`
  - 密钥信息：`tests/exp1_tx_nodes/data/nodes_<nodes>/node<i>/key_info.json`
- 节点日志目录：`tests/exp1_tx_nodes/logs/nodes_<nodes>/`
  - 节点日志：`node<i>.log`
  - gentx 等过程日志：`gentx_node<i>.log`、`collect_gentxs.log`
- 节点二进制（启动脚本构建输出）：`tests/exp1_tx_nodes/bin/hcpd`

端口说明（本地多进程同 IP 场景）：
- `PORT_OFFSET` 用于避免端口冲突；第一个节点的常用端口：
  - CometBFT RPC：`26657 + PORT_OFFSET`
  - gRPC：`9090 + PORT_OFFSET`
  - P2P：`26656 + PORT_OFFSET`
  - 其余节点在此基础上按固定步长错开，详见启动脚本 [start_nodes.sh](file:///home/hcp-dev/hcp-project-experiment/hcp/start_nodes.sh)。
