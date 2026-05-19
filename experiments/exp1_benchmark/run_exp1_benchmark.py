#!/usr/bin/env python3
"""实验1：基准对比实验 (表4-2)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_runner import (
    run_benchmark, avg, stdev, ci95, format_stat,
    save_json, save_md, copy_to_report, TESTS_DIR
)


def main():
    outdir = TESTS_DIR / "exp1_benchmark"
    outdir.mkdir(parents=True, exist_ok=True)

    engines = ["pbft", "tpbft", "hotstuff", "raft", "cometbft"]
    nodes_list = [8, 16, 32]
    tx_count = 1000
    repeat = 5  # 5次重复，计算统计量

    print("[EXP1] 基准对比实验开始 (repeat=5)")
    matrix = {}
    for engine in engines:
        matrix[engine] = {}
        for nodes in nodes_list:
            runs = []
            for r in range(1, repeat + 1):
                print(f"  {engine} nodes={nodes} run={r}/{repeat}")
                res = run_benchmark(engine, nodes, tx_count, outdir, f"_r{r}")
                if res:
                    runs.append(res)
            if runs:
                tps_vals = [r["TPS"] for r in runs]
                p99_vals = [r["P99LatencyMs"] for r in runs]
                msgs_vals = [r["TotalMessages"] for r in runs]
                matrix[engine][nodes] = {
                    "tps_mean": avg(tps_vals),
                    "tps_std": stdev(tps_vals),
                    "tps_ci_lo": ci95(tps_vals)[0],
                    "tps_ci_hi": ci95(tps_vals)[1],
                    "p99_mean": avg(p99_vals),
                    "p99_std": stdev(p99_vals),
                    "p99_ci_lo": ci95(p99_vals)[0],
                    "p99_ci_hi": ci95(p99_vals)[1],
                    "msgs_mean": avg(msgs_vals),
                    "msgs_std": stdev(msgs_vals),
                    "raw": runs,
                }

    save_json(matrix, outdir / "summary.json")

    md = ["## 表4-2 基准对比实验完整矩阵 (n=5, mean±std [95% CI])\n",
          "| 算法 | 节点数 | TPS | P50(ms) | P95(ms) | P99(ms) | 消息数 |",
          "|------|--------|-----|---------|---------|---------|--------|"]
    for engine in engines:
        for nodes in nodes_list:
            if nodes in matrix.get(engine, {}):
                d = matrix[engine][nodes]
                md.append(
                    f"| {engine} | {nodes} | "
                    f"{d['tps_mean']:.2f}±{d['tps_std']:.2f} | "
                    f"{avg([r['P50LatencyMs'] for r in d['raw']]):.2f} | "
                    f"{avg([r['P95LatencyMs'] for r in d['raw']]):.2f} | "
                    f"{d['p99_mean']:.2f}±{d['p99_std']:.2f} | "
                    f"{int(d['msgs_mean'])}±{int(d['msgs_std'])} |"
                )
    save_md(md, outdir / "table4_2.md")
    copy_to_report(outdir, "exp1_benchmark")
    print("[EXP1] 完成")


if __name__ == "__main__":
    main()
