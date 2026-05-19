# 实验3：tPBFT 并行 Merkle Hash（真实交易）

## 实验内容
- 目的：在 tPBFT 的“并行 Merkle 子块（parallel block）”实现下，改变 `k`（子块数量/并行度）与交易数，评估区块处理时间（T_block）、加速比（speedup）、效率（efficiency）等指标。
- 自变量：
  - `k`：并行子块数量（默认 `1,2,4,8`）
  - `tx`：交易总数（默认 `1000,5000,10000`）
  - `repeat`：每个 (tx,k) 重复次数（默认 `30`）
  - `nodes`：节点数（默认 `1`，用于单机测量计算开销）
- 特点：该实验会在每次运行前设置环境变量：
  - `CONSENSUS_ENGINE=tpbft-parallel-block`
  - `MERKLE_K=<k>`
  以启用并行 Merkle 相关逻辑（见 [run_exp3_tpbft_parallel_block.py](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp3_parallel_merkle/run_exp3_tpbft_parallel_block.py#L74-L76)）。

## 如何运行
- 入口脚本：[run_exp3_parallel_merkle.sh](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp3_parallel_merkle/run_exp3_parallel_merkle.sh)

```bash
bash hcp-lab/experiments/exp3_parallel_merkle/run_exp3_parallel_merkle.sh
```

可通过环境变量覆盖默认参数：

```bash
K_LIST="1,2,4" TX_LIST="1000,5000" REPEAT=10 NODE_COUNT=1 PORT_OFFSET=3100 CHAIN_ID="hcp-exp3" \
  bash hcp-lab/experiments/exp3_parallel_merkle/run_exp3_parallel_merkle.sh
```

## 实验文件夹用途说明
- `run_exp3_parallel_merkle.sh`：设置默认参数并转调测试脚本。
- `test_exp3_tpbft_parallel_block.sh`：构建 `hcp-loadgen`，设置实验产物目录，调用 Python 驱动脚本。
- `run_exp3_tpbft_parallel_block.py`：实验主逻辑（手动启动/停止节点、触发 loadgen、采集日志与系统指标、计算 speedup/efficiency、输出报告与图表）。
- `run_exp3_parallel_merkle.py / run_exp3_tpbft_parallel.py / run_exp3.py`：其他实验驱动脚本（用于不同版本/对照用法），当前入口脚本默认使用 `run_exp3_tpbft_parallel_block.py`。
- `report/`：实验输出目录（由脚本参数 `--out` 决定），包含：
  - `result.json`：结构化结果（包含每个 (tx,k) 的均值指标）
  - `report.md` / `report.pdf` / `report.tex`
  - `figures/*.svg`：每个 tx 对应的 T_block/speedup/efficiency 曲线

## 中间文件与路径约定
实验会在项目根目录下写入中间产物（可由 `EXP_ARTIFACT_ROOT` 覆盖）。本实验默认：
- 实验产物根目录：`tests/exp3_parallel_merkle`
- 每个 (tx,k,run) 的产物目录：
  - 数据（节点 home、账户等）：`tests/exp3_parallel_merkle/data_tx_<tx>/k_<k>/run_<i>/`
    - 节点 home：`.../node<j>/`
    - 负载账户文件：`.../accounts.jsonl`
  - 日志：`tests/exp3_parallel_merkle/logs_tx_<tx>/k_<k>/run_<i>/`
    - 节点日志：`node<j>.log`
    - gentx 等过程日志：`gentx_node<j>.log`、`collect_gentxs.log`
- 节点二进制（启动脚本构建输出）：`tests/exp3_parallel_merkle/bin/hcpd`

端口说明：
- `PORT_OFFSET` 用于避免端口冲突；常用端口为：
  - CometBFT RPC：`26657 + PORT_OFFSET`
  - gRPC：`9090 + PORT_OFFSET`
