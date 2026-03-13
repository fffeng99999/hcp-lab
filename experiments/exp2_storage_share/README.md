# 实验2：共享存储规模变化对共识吞吐的影响

## 实验内容
- 目的：在固定总节点数与固定交易负载下，改变“共享存储规模（share size）”，观察 TPS、提交延迟、写放大、Compaction、IO util 等指标变化。
- 自变量：
  - `share_size`：共享规模列表（默认 `2,4,8,16`）
  - `nodes`：总节点数（默认 `32`）
  - `tx`：交易总数（默认 `10000`）
  - `repeat`：每组参数重复次数（默认 `3`）
- 输出：除常规 TPS/延迟/CPU/网络外，还会生成多张 SVG 曲线图（如 share vs TPS/WA/Compaction/Commit/IOUtil）。

## 如何运行
- 入口脚本：[run_exp2_storage_share.sh](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp2_storage_share/run_exp2_storage_share.sh)

```bash
bash hcp-lab/experiments/exp2_storage_share/run_exp2_storage_share.sh
```

可通过环境变量覆盖默认参数：

```bash
SHARES="2,4,8" NODE_COUNT=32 TX_COUNT=20000 REPEAT=5 PORT_OFFSET=2100 CHAIN_ID="hcp-exp2" \
  bash hcp-lab/experiments/exp2_storage_share/run_exp2_storage_share.sh
```

## 实验文件夹用途说明
- `run_exp2_storage_share.sh`：设置默认参数并转调测试脚本。
- `test_exp2_storage_share.sh`：构建 `hcp-loadgen`，设置实验产物目录，启动实验执行器（Python）。
- `run_exp2.py`：实验编排与聚合逻辑（对每个 share_size 重复运行并做均值聚合，输出图表与报告）。
- `report/`：实验输出目录（由脚本参数 `--out` 决定），包含：
  - `result.json`（若脚本输出）：结构化结果
  - `report.md` / `report.pdf` / `report.tex`：报告
  - `figures/*.svg`：曲线图（在 Markdown 中引用）

## 中间文件与路径约定
实验会在项目根目录下写入中间产物（可由 `EXP_ARTIFACT_ROOT` 覆盖）。本实验默认：
- 实验产物根目录：`tests/exp2_storage_share`
- 每个 share_size、每次 repeat 的产物目录：
  - 数据：`tests/exp2_storage_share/data_share_<share>/run_<i>/`
  - 日志：`tests/exp2_storage_share/logs_share_<share>/run_<i>/`
- 节点数据目录（由实验执行器再按节点数分层）：
  - `.../data_share_<share>/run_<i>/nodes_<nodes>/node<j>/`
  - `.../data_share_<share>/run_<i>/nodes_<nodes>/accounts.jsonl`
- 节点日志目录：
  - `.../logs_share_<share>/run_<i>/nodes_<nodes>/node<j>.log`
  - `.../logs_share_<share>/run_<i>/nodes_<nodes>/*gentx*` 等过程日志
- 节点二进制（启动脚本构建输出）：`tests/exp2_storage_share/bin/hcpd`

端口说明：
- `PORT_OFFSET` 用于避免端口冲突；常用端口为：
  - CometBFT RPC：`26657 + PORT_OFFSET`
  - gRPC：`9090 + PORT_OFFSET`
