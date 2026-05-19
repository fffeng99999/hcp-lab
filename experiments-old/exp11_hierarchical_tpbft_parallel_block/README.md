# 实验十一：分层 TPBFT + 并行 Merkle 块

## 实验目标

验证**分层 TPBFT 共识**与**并行 Merkle 块计算**两种机制叠加后的综合性能表现。

- **分层 TPBFT**：通过双层共识结构（内层组内共识 + 外层代表共识）将通信复杂度从 O(N²) 降至 O(N + g)，并支持签名瓶颈的灵活迁移。
- **并行 Merkle 块**：将区块内交易按 k 个子块并行计算 Merkle 根，加速区块哈希验证。

本实验探索两种优化机制在真实交易场景下的协同效果。

## 自变量

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `groups` (g) | 分组数量 | 32,16,8,4,2 |
| `k` | 并行 Merkle 子块数 | 1,2,4,8 |
| `sig_algos` | 签名算法 | bls,ed25519 |
| `nodes` | 总节点数 | 4 |
| `tx` | 每轮交易数 | 100 |
| `repeat` | 重复次数 | 5 |

## 因变量

### 分层 TPBFT 指标
- `pre_prepare_ms` / `prepare_ms` / `commit_ms`：三阶段耗时
- `comm_bytes` / `total_messages`：通信量
- `sig_gen_time_ms` / `sig_verify_time_ms` / `aggregation_time_ms`：签名操作耗时
- `sig_ops_per_tx`：每笔交易的签名操作数

### 并行 Merkle 块指标
- `block_time_ms`：总 Merkle 计算耗时
- `subblock_time_ms`：子块并行计算耗时
- `merge_time_ms`：子根合并耗时
- `speedup`：相对于 k=1 的加速比
- `efficiency`：并行效率

### 综合指标
- `tps`：实际吞吐量
- `cpu_percent`：CPU 使用率
- `net_mbps`：网络带宽

## 产物路径

```
tests/exp11_hierarchical_tpbft_parallel_block/
├── algo_<algo>/g_<g>/k_<k>/run_<i>/data/   # 节点数据
└── algo_<algo>/g_<g>/k_<k>/run_<i>/logs/   # 节点日志

hcp-lab/experiments/exp11_hierarchical_tpbft_parallel_block/report/
├── result.json
├── exp11_summary.csv
├── figures/
│   ├── tps_vs_g_<algo>_k<k>.svg
│   ├── sig_time_vs_g_<algo>_k<k>.svg
│   ├── merkle_time_vs_k_<algo>_g<g>.svg
│   ├── speedup_vs_k_<algo>_g<g>.svg
│   └── efficiency_vs_k_<algo>_g<g>.svg
└── report.md
```

## 运行方式

```bash
cd hcp-lab/experiments/exp11_hierarchical_tpbft_parallel_block
bash run_exp11.sh
```

或通过 hcp-lab-server UI 选择实验十一执行。

## 引擎

共识引擎：`hierarchical-tpbft-parallel-block`
