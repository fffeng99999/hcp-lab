#!/usr/bin/env python3
"""实验2：退化率计算 (表4-3)"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_runner import save_json, save_md, copy_to_report, TESTS_DIR


def main():
    outdir = TESTS_DIR / "exp2_degradation"
    outdir.mkdir(parents=True, exist_ok=True)

    exp1_file = TESTS_DIR / "exp1_benchmark" / "summary.json"
    if not exp1_file.exists():
        print("[EXP2] 错误：缺少EXP1数据，请先运行EXP1")
        return

    matrix = json.loads(exp1_file.read_text())
    print("[EXP2] 退化率计算开始")

    deg = {}
    for engine, data in matrix.items():
        if "8" in data and "32" in data:
            tps8 = data["8"]["tps_mean"]
            tps32 = data["32"]["tps_mean"]
            deg[engine] = {
                "r_deg": (tps8 - tps32) / tps8 * 100,
                "tps8": tps8,
                "tps32": tps32,
            }
            print(f"  {engine}: R_deg={deg[engine]['r_deg']:.2f}%")

    save_json(deg, outdir / "summary.json")
    md = ["## 表4-3 退化率计算\n", "| 算法 | TPS(8节点) | TPS(32节点) | R_deg (%) |", "|------|------------|-------------|-----------|"]
    for engine, v in deg.items():
        md.append(f"| {engine} | {v['tps8']:.2f} | {v['tps32']:.2f} | {v['r_deg']:.2f} |")
    save_md(md, outdir / "table4_3.md")
    copy_to_report(outdir, "exp2_degradation")
    print("[EXP2] 完成")


if __name__ == "__main__":
    main()
