## 表3-3 CometBFT 与 CometBFT-light 对比

统一负载：Uniform，tx=1000，约250 bytes/tx。CometBFT 为官方 CometBFT/Cosmos SDK 多进程节点；CometBFT-light 为 HCP engine 轻量实现。

| 算法 | 节点数N | TPS(tx/s) | P50(ms) | P95(ms) | P99(ms) | 成功率 |
|------|---------|-----------|---------|---------|---------|--------|
| CometBFT | 8 | 17.86±0.00 | 0.57±0.00 | 4.90±0.00 | 6.57±0.00 | 1.000 |
| CometBFT-light | 8 | 2559.13±297.35 | 185.33±31.60 | 359.79±22.89 | 390.43±48.30 | 1.000 |