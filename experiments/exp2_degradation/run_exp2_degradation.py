#!/usr/bin/env python3
"""实验2：规模退化率计算。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import clean_report, save_json, save_md


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "report"
EXP1_SUMMARY = SCRIPT_DIR.parent / "exp1_benchmark" / "report" / "summary.json"


def main() -> None:
    clean_report(REPORT_DIR)
    if not EXP1_SUMMARY.exists():
        raise SystemExit("[EXP2] 缺少 EXP1 最终数据，请先运行 exp1_benchmark")
    matrix = json.loads(EXP1_SUMMARY.read_text(encoding="utf-8"))
    deg = {}
    for engine, by_nodes in matrix.items():
        if "8" not in by_nodes or "32" not in by_nodes:
            continue
        tps8 = float(by_nodes["8"].get("tps_mean", 0.0))
        tps32 = float(by_nodes["32"].get("tps_mean", 0.0))
        if tps8 <= 0:
            continue
        deg[engine] = {
            "tps8": tps8,
            "tps32": tps32,
            "r_deg": (tps8 - tps32) / tps8 * 100.0,
            "p99_8": float(by_nodes["8"].get("p99_mean", 0.0)),
            "p99_32": float(by_nodes["32"].get("p99_mean", 0.0)),
        }
    save_json(deg, REPORT_DIR / "summary.json")
    md = [
        "## 表4-3 规模退化率计算",
        "",
        "| 算法 | TPS(8节点) | TPS(32节点) | R_deg(%) | P99(8节点) | P99(32节点) |",
        "|------|------------|-------------|----------|------------|-------------|",
    ]
    for engine, v in deg.items():
        md.append(
            f"| {engine} | {v['tps8']:.2f} | {v['tps32']:.2f} | {v['r_deg']:.2f} | "
            f"{v['p99_8']:.2f} | {v['p99_32']:.2f} |"
        )
    save_md(md, REPORT_DIR / "table4_3.md")
    print("[EXP2] 完成", flush=True)


if __name__ == "__main__":
    main()
