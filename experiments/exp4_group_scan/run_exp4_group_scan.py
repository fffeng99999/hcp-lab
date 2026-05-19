#!/usr/bin/env python3
"""实验4：分组参数扫描 (表4-5, 4-6)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_runner import run_benchmark_group, save_json, save_md, copy_to_report, TESTS_DIR


def main():
    outdir = TESTS_DIR / "exp4_group_scan"
    outdir.mkdir(parents=True, exist_ok=True)

    nodes = 32
    tx_count = 1000
    groups = [1, 2, 4, 8, 16]
    results = {}

    print("[EXP4] 分组参数扫描开始")
    for g in groups:
        if nodes % g != 0:
            continue
        print(f"  groups={g}")
        res = run_benchmark_group("hierarchical_tpbft", nodes, g, tx_count, outdir)
        if res:
            results[g] = {
                "tps": res.get("TPS", 0),
                "p99": res.get("P99LatencyMs", 0),
                "msgs": res.get("TotalMessages", 0),
            }

    save_json(results, outdir / "summary.json")

    md5 = ["## 表4-5 分组参数扫描 (N=32)\n",
           "| K | M | TPS | P99(ms) | 消息数 |",
           "|---|---|-----|---------|--------|"]
    for g in groups:
        if g in results:
            d = results[g]
            md5.append(f"| {g} | {nodes//g} | {d['tps']:.2f} | {d['p99']:.2f} | {int(d['msgs'])} |")
    save_md(md5, outdir / "table4_5.md")

    md6 = ["## 表4-6 分层复杂度理论验证 (N=32)\n",
           "| K | M | 理论消息数 | 实测消息数 | 误差(%) |",
           "|---|---|------------|------------|---------|"]
    for g in groups:
        if g in results:
            theory = g * (nodes//g) * ((nodes//g)-1) * 2 + g * (g-1) * 2
            actual = results[g]["msgs"]
            md6.append(f"| {g} | {nodes//g} | {theory} | {int(actual)} | - |")
    save_md(md6, outdir / "table4_6.md")

    copy_to_report(outdir, "exp4_group_scan")
    print("[EXP4] 完成")


if __name__ == "__main__":
    main()
