# 实验2：tPBFT 共识性能与节点规模扩展性测试

## 实验内容
- 目的：在固定交易负载下，改变节点规模，评估 tPBFT（Trust-enhanced Practical Byzantine Fault Tolerance）共识算法的 TPS、延迟（含 P99）、资源占用等指标变化。
- 自变量：
  - `nodes`：节点数（默认 `4,8,16,32`）
  - `tx`：交易总数（默认 `100,1000,10000`）
  - `repeat`：每组参数重复次数（默认 `3`）
- 因变量（采集输出）：`tps`、`avg_confirm_time_ms`、`p50/p95/p99`、`avg_block_time_ms`、`cpu_percent`、`net_mbps`、`io_util`、RocksDB 写入耗时与写放大等。

## tPBFT 共识算法详解

### 1. 算法背景

tPBFT（Trust-enhanced Practical Byzantine Fault Tolerance）是一种基于 PBFT 改进的联盟链共识算法，引入**信任评分机制（Trust Scoring）**与**动态验证人选择（Validator Selection）**，在保持 PBFT 强一致性的同时提升共识效率与安全性。

### 2. PBFT 基础三阶段

tPBFT 保留了经典 PBFT 的核心共识流程：

1. **PrePrepare 阶段**：主节点（Primary）将客户端请求打包为提案，广播 PrePrepare 消息给所有副本节点（Replicas）。消息格式包含视图号 `v`、序列号 `n`、请求摘要 `d` 及原始请求 `m`。
2. **Prepare 阶段**：副本节点收到 PrePrepare 后验证提案有效性，广播 Prepare 消息给其他节点。当某节点收到至少 `2f` 个来自不同节点的 Prepare 消息时，进入 Prepared 状态。
3. **Commit 阶段**：Prepared 节点广播 Commit 消息。当收到至少 `2f+1` 个 Commit 消息后，节点执行请求并提交区块。

经典 PBFT 的容错边界为 `f ≤ (N-1)/3`，通信复杂度为 `O(N²)`。

### 3. tPBFT 信任评分机制

tPBFT 的核心创新在于引入**多维信任评分模型**，对验证人节点进行动态评估：

#### 3.1 评分维度
- **成功率（SuccessRate）**：权重 40%。统计节点历史共识参与的成功比例，基于滑动窗口（默认 100 条记录）计算。
- **质押权重（StakeWeight）**：权重 30%。节点质押金额占全网总质押的比例，反映经济承诺。
- **响应速度（ResponseSpeed）**：权重 30%。基于历史响应时间计算，理想响应为 100ms，超过 1000ms 降至最低分 0.1，中间区间线性衰减。

#### 3.2 总信任分计算公式
```
TotalScore = SuccessRate * 0.4 + StakeWeight * 0.3 + ResponseSpeed * 0.3
```

#### 3.3 评分更新时机
- **BeginBlock**：当节点作为提议者出块时，根据其出块行为更新信任分（成功出块加分）。
- **EndBlock**：在每个区块结束时，根据所有验证人的投票签名情况更新信任分（参与签名加分，缺席减分）。

### 4. 动态验证人选择

tPBFT 不强制所有节点参与共识，而是通过 **ValidatorSelector** 动态筛选高信任节点：

1. **阈值过滤**：设定最小信任分阈值（默认 `minTrust = 0.6`），低于阈值的节点被排除在共识组外。
2. **排序择优**：按总信任分从高到低排序。
3. **随机化选择**：从排序后的列表中选取验证人，其中 **70% 来自高分段**，**30% 从剩余节点中随机抽取**，避免共识组固化。
4. **数量限制**：最大验证人数量可配置（默认 `maxValidators = 100`），超出部分不进入共识组。

### 5. 容错分析

- **共识组内容错**：设共识组规模为 `M = d * N`（`d` 为参与比例），则共识组内可容忍的拜占庭节点数为 `f ≤ (M-1)/3`。
- **全网容错**：由于低信任节点被排除在共识组外，即使它们全部作恶也不影响共识。因此全网最大可容忍拜占庭节点数为：
  ```
  f_total = (d*N - 1)/3 + (1-d)*N = (1 - 2d/3)*N - 1/3
  ```
  当 `d=1`（所有节点参与）时退化为经典 PBFT 的 `(N-1)/3`；当 `d<1` 时，全网容错率**高于**经典 PBFT。

### 6. 通信复杂度

- **最优情况**：仅高信任节点参与共识，消息量为 `O((d*N)²)`，`d<1` 时显著低于 `O(N²)`。
- **最坏情况**：`d=1` 时与经典 PBFT 相同，为 `O(N²)`。

### 7. 视图变更优化

tPBFT 通过信任评分机制降低了主节点作恶或故障导致视图变更（View Change）的概率：
- 主节点由共识组内信任分最高的节点担任。
- 若主节点信任分骤降，系统可在不触发完整视图变更的情况下，通过 ValidatorSelector 的下一轮选择自然轮换主节点。

## 如何运行
- 入口脚本：[run_exp2_tpbft.sh](file:///home/hcp-dev/hcp-project-experiment/hcp-lab/experiments/exp2_tpbft/run_exp2_tpbft.sh)

```bash
bash hcp-lab/experiments/exp2_tpbft/run_exp2_tpbft.sh
```

可通过环境变量覆盖默认参数：

```bash
NODES_LIST="4,8,16" TX_LIST="100,1000" REPEAT=5 PORT_OFFSET=2100 CHAIN_ID="hcp-exp2" \
  TPBFT_MIN_TRUST=0.5 TPBFT_MAX_VALIDATORS=50 \
  bash hcp-lab/experiments/exp2_tpbft/run_exp2_tpbft.sh
```

## 实验文件夹用途说明
- `run_exp2_tpbft.sh`：设置默认参数并转调测试脚本。
- `test_exp2_tpbft.sh`：构建 `hcp-loadgen`，设置实验产物目录，启动实验执行器（Python）。
- `run_exp2.py`：实验编排与聚合逻辑（对每个节点数×交易量组合重复运行并做均值聚合，输出图表与报告）。
- `report/`：实验输出目录（由脚本参数 `--out` 决定），包含：
  - `result.json`：结构化实验结果
  - `exp2_summary.csv`：聚合后的 CSV 数据
  - `report.md` / `report.pdf` / `report.tex`：报告（PDF 若缺 LaTeX 引擎可能为 None）
  - `figures/*.svg`：性能曲线图

## 中间文件与路径约定
实验会在项目根目录下写入中间产物（可由 `EXP_ARTIFACT_ROOT` 覆盖）。本实验默认：
- 实验产物根目录：`tests/exp2_tpbft`
- 每个实验点（节点数 n、交易数 tx、第 i 次重复）的产物目录：
  - 数据：`tests/exp2_tpbft/n_<n>/tx_<tx>/run_<i>/data/`
  - 日志：`tests/exp2_tpbft/n_<n>/tx_<tx>/run_<i>/logs/`
- 节点数据目录（由实验执行器再按节点数分层）：
  - `.../data/nodes_<nodes>/node<j>/`
  - `.../data/nodes_<nodes>/accounts.jsonl`
- 节点日志目录：
  - `.../logs/nodes_<nodes>/node<j>.log`
  - `.../logs/nodes_<nodes>/*gentx*` 等过程日志
- 节点二进制（启动脚本构建输出）：`tests/exp2_tpbft/bin/hcpd`

端口说明：
- `PORT_OFFSET` 用于避免端口冲突；常用端口为：
  - CometBFT RPC：`26657 + PORT_OFFSET`
  - gRPC：`9090 + PORT_OFFSET`
  - P2P：`26656 + PORT_OFFSET`
