# 实验十三：子组轻量共识变体 TPBFT

## 实验目标

验证在分层 TPBFT 架构中，将**子层共识从 PBFT 替换为 Raft（CFT）**后对整体性能的影响。

- **子层 PBFT（基线）**：子组内部运行完整的三阶段 PBFT（Pre-prepare/Prepare/Commit），通信轮次多、消息量大。
- **子层 Raft（优化）**：子组内部运行 Raft（Leader 复制 + Follower 确认），通信轮次从 3 轮压缩为 1 轮有效复制，消息量下降约 40%–60%。

核心假设：**子层通信是分层架构的主要瓶颈之一**，将子层从 BFT 降级为 CFT 可在许可链场景下显著提升吞吐并降低延迟。

## 自变量

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `groups` (g) | 分组数量 | 32,16,8,4,2 |
| `sub_consensus` | 子层共识类型 | pbft, raft |
| `sig_algos` | 签名算法 | bls,ed25519 |
| `nodes` | 总节点数 | 4 |
| `tx` | 每轮交易数 | 100 |
| `repeat` | 重复次数 | 5 |

## 因变量

### 共识指标
- `pre_prepare_ms` / `prepare_ms` / `commit_ms`：三阶段耗时
- `comm_bytes` / `total_messages`：通信量
- `sig_gen_time_ms` / `sig_verify_time_ms` / `aggregation_time_ms`：签名操作耗时

### 子层轻量共识核心指标
- `sub_messages`：子层总消息数（PBFT 子层 vs Raft 子层对比）
- `sub_pre_prepare_ms` / `sub_prepare_ms` / `sub_append_ms`：子层各阶段耗时
- `recovery_time_ms`：故障注入后的恢复时间（仅 Raft 故障组）
- `fault_injected`：是否注入故障（0/1）

### 综合指标
- `tps`：实际吞吐量
- `cpu_percent`：CPU 使用率
- `net_mbps`：网络带宽

## 实验矩阵（A/B/C/D 四组）

| 实验组 | 节点数 | 子层共识 | 主层共识 | 故障注入 | 核心目的 |
|--------|--------|----------|----------|----------|----------|
| **A-基线** | 16, 32 | PBFT | PBFT | 无 | 现有分层 TPBFT 标准表现 |
| **B-轻量优化** | 16, 32 | **Raft** | PBFT | 无 | **核心实验组**：验证子层 CFT 对吞吐的提升 |
| **C-故障恢复** | 32 | **Raft** | PBFT | 子层 Leader 崩溃（60s 后） | 验证 CFT 下的恢复能力与活性代价 |
| **D-主层升级**（可选） | 16 | Raft | **HotStuff** | 无 | 验证子层简化 + 主层流水线化的叠加效果 |

每组重复 5 次，取均值与标准差。

## 产物路径

```
tests/exp13_lightweight_tpbft/
├── algo_<algo>/g_<g>/sub_<sub>/run_<i>/data/
└── algo_<algo>/g_<g>/sub_<sub>/run_<i>/logs/

hcp-lab/experiments/exp13_lightweight_tpbft/report/
├── result.json
├── exp13_summary.csv
├── figures/
│   ├── tps_vs_g_<algo>_sub<pbft/raft>.svg
│   ├── sub_messages_vs_g_<algo>.svg
│   ├── commit_ms_vs_g_<algo>.svg
│   ├── fault_recovery_tps_32nodes_<algo>.svg
│   └── latency_boxplot_<algo>.svg
└── report.md
```

## 运行方式

```bash
cd hcp-lab/experiments/exp13_lightweight_tpbft
bash run_exp13.sh
```

或通过 hcp-lab-server UI 选择实验十三执行。

## 共识引擎

共识引擎：`hierarchical-lightweight-tpbft`

## Trade-off 声明

子层 Raft 仅提供 CFT（崩溃容错），不提供 BFT（拜占庭容错）。本文明确限定在**许可链场景**下使用——子组节点由同一机构或受控联盟成员运行，拜占庭攻击假设弱于公链，该 trade-off 可接受。
