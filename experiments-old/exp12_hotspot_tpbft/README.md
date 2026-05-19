# 实验十二：热点账户感知分组 TPBFT

## 实验目标

验证在**热点账户负载**（Zipf 分布）下，不同分组策略对分层 TPBFT 共识性能的影响。

- **Random 分组**：账户随机分配到各子组，热点账户的交易可能分散到多个子组，产生大量跨组事务。
- **Hotspot 感知分组**：按账户哈希路由到固定子组，同一账户的所有交易落入同一子组，显著降低跨组率。

核心假设：**跨组交易是分层共识的瓶颈**，热点感知分组可将跨组率从 ~40%–55% 压降至 <5%，从而恢复/提升 TPS。

## 自变量

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `groups` (g) | 分组数量 | 32,16,8,4,2 |
| `strategy` | 分组策略 | random, hotspot |
| `zipf_alpha` | Zipf 分布偏斜度 | 0.0, 1.5, 1.8, 2.0 |
| `sig_algos` | 签名算法 | bls,ed25519 |
| `nodes` | 总节点数 | 4 |
| `tx` | 每轮交易数 | 100 |
| `repeat` | 重复次数 | 5 |

## 因变量

### 共识指标
- `pre_prepare_ms` / `prepare_ms` / `commit_ms`：三阶段耗时（commit 含跨组惩罚）
- `comm_bytes` / `total_messages`：通信量
- `sig_gen_time_ms` / `sig_verify_time_ms` / `aggregation_time_ms`：签名操作耗时

### 热点感知核心指标
- `cross_group_ratio`：**跨组交易率**（0–1），核心解释变量
- `merkle_speedup` / `merkle_efficiency`：（如结合并行 Merkle）

### 综合指标
- `tps`：实际吞吐量
- `cpu_percent`：CPU 使用率
- `net_mbps`：网络带宽

## 实验矩阵（A/B/C/D 四组）

| 实验组 | 节点数 | 分组策略 | Zipf α | 负载模式 | 目的 |
|--------|--------|----------|--------|----------|------|
| **A-对照** | 16, 32 | Random | 0.0 (Uniform) | Sustained | 基线：现有分层 TPBFT 标准表现 |
| **B-热点随机** | 16, 32 | Random | 1.8 | Sustained | 验证「热点负载 + 随机分组」的恶化程度 |
| **C-热点感知** | 16, 32 | Hotspot | 1.8 | Sustained | **核心实验组**：验证优化效果 |
| **D-α 敏感度** | 32 | Hotspot | 1.2, 1.5, 1.8, 2.2 | Sustained | 验证热点集中度对 TPS 的边际影响 |

每组重复 5 次，取均值与标准差。

## 产物路径

```
tests/exp12_hotspot_tpbft/
├── algo_<algo>/g_<g>/strategy_<strategy>/alpha_<alpha>/run_<i>/data/
└── algo_<algo>/g_<g>/strategy_<strategy>/alpha_<alpha>/run_<i>/logs/

hcp-lab/experiments/exp12_hotspot_tpbft/report/
├── result.json
├── exp12_summary.csv
├── figures/
│   ├── tps_vs_g_<algo>_alpha<alpha>.svg
│   ├── commit_ms_vs_g_<algo>_alpha<alpha>.svg
│   ├── cross_group_ratio_vs_g_<algo>_alpha<alpha>.svg
│   ├── tps_vs_alpha_32nodes_<algo>.svg
│   └── commit_vs_alpha_32nodes_<algo>.svg
└── report.md
```

## 运行方式

```bash
cd hcp-lab/experiments/exp12_hotspot_tpbft
bash run_exp12.sh
```

或通过 hcp-lab-server UI 选择实验十二执行。

## 共识引擎

共识引擎：`hierarchical-hotspot-tpbft`

负载生成：支持 `--account-selection-mode zipf --zipf-alpha <alpha>`
