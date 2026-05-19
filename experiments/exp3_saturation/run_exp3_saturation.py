#!/usr/bin/env python3
"""实验3：饱和边界初探 (表4-4)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_runner import (
    run_benchmark, avg, stdev, ci95,
    save_json, save_md, copy_to_report, TESTS_DIR
)


def main():
    outdir = TESTS_DIR / "exp3_saturation"
    outdir.mkdir(parents=True, exist_ok=True)

    engines = ["pbft", "tpbft", "hotstuff", "raft", "cometbft"]
    nodes = 16
    repeat = 5  # 每个lambda点重复5次
    results = {}

    print("[EXP3] 饱和边界初探开始 (repeat=5)")
    for engine in engines:
        results[engine] = {}
        for lam in range(20, 121, 20):
            tx_count = lam * 10
            runs = []
            for r in range(1, repeat + 1):
                print(f"  {engine} lambda={lam} run={r}/{repeat}")
                res = run_benchmark(engine, nodes, tx_count, outdir, f"_lam{lam}_r{r}")
                if res:
                    runs.append(res)
            if runs:
                tps_vals = [r["TPS"] for r in runs]
                p99_vals = [r["P99LatencyMs"] for r in runs]
                results[engine][lam] = {
                    "tps_mean": avg(tps_vals),
                    "tps_std": stdev(tps_vals),
                    "tps_ci": ci95(tps_vals),
                    "p99_mean": avg(p99_vals),
                    "p99_std": stdev(p99_vals),
                    "p99_ci": ci95(p99_vals),
                    "raw": runs,
                }

    save_json(results, outdir / "summary.json")
    md = ["## 表4-4 饱和边界初探 (N=16, n=5, mean±std [95% CI])\n",
          "| 算法 | λ=20 | λ=40 | λ=60 | λ=80 | λ=100 | λ=120 |",
          "|------|------|------|------|------|-------|-------|"]
    for engine in engines:
        row = [engine]
        for lam in range(20, 121, 20):
            d = results[engine].get(lam, {})
            row.append(f"{d.get('tps_mean', 0):.2f}±{d.get('tps_std', 0):.2f}")
        md.append("| " + " | ".join(row) + " |")
    save_md(md, outdir / "table4_4.md")
    copy_to_report(outdir, "exp3_saturation")
    print("[EXP3] 完成")


if __name__ == "__main__":
    main()
