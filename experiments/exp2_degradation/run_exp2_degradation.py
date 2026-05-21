#!/usr/bin/env python3
"""Experiment 2: derive the 8-to-32 node scalability degradation table."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import clean_report, save_json, save_md


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "report"
EXP1_SUMMARY = SCRIPT_DIR.parent / "exp1_benchmark" / "report" / "summary.json"

ENGINE_ORDER = ["pbft", "hotstuff", "raft", "cometbft-light", "tpbft"]
ENGINE_LABELS = {
    "pbft": "PBFT",
    "hotstuff": "HotStuff",
    "raft": "Raft",
    "cometbft-light": "CometBFT-light",
    "tpbft": "tPBFT",
}
DEGRADATION_FACTORS = {
    "pbft": "全量广播消息复杂度随节点数上升",
    "hotstuff": "领导者聚合与流水线提交开销",
    "raft": "领导者日志复制与心跳维护开销",
    "cometbft-light": "类 Tendermint 多轮投票广播开销",
    "tpbft": "信任评分缓解部分广播压力",
}


def main() -> None:
    clean_report(REPORT_DIR)
    if not EXP1_SUMMARY.exists():
        raise SystemExit("[EXP2] missing exp1 summary, run exp1_benchmark first")

    matrix = json.loads(EXP1_SUMMARY.read_text(encoding="utf-8"))
    summary = {}
    for engine in ENGINE_ORDER:
        by_nodes = matrix.get(engine, {})
        if "8" not in by_nodes or "32" not in by_nodes:
            continue
        tps8 = float(by_nodes["8"].get("tps_mean", 0.0))
        tps32 = float(by_nodes["32"].get("tps_mean", 0.0))
        if tps8 <= 0:
            continue
        summary[engine] = {
            "label": ENGINE_LABELS.get(engine, engine),
            "tps8": tps8,
            "tps32": tps32,
            "r_deg_percent": (tps8 - tps32) / tps8 * 100.0,
            "dominant_factor": DEGRADATION_FACTORS.get(engine, "待结合日志分析"),
        }

    save_json(summary, REPORT_DIR / "summary.json")

    md = [
        "## 表3-6 规模扩展退化率计算",
        "",
        "| 算法 | TPS8 | TPS32 | Rdeg (%) | 退化主导因素 |",
        "|------|------|-------|----------|--------------|",
    ]
    for engine in ENGINE_ORDER:
        item = summary.get(engine)
        if not item:
            continue
        md.append(
            f"| {item['label']} | {item['tps8']:.2f} | {item['tps32']:.2f} | "
            f"{item['r_deg_percent']:.2f}% | {item['dominant_factor']} |"
        )

    save_md(md, REPORT_DIR / "table3_6.md")
    print(f"[EXP2] wrote {REPORT_DIR / 'table3_6.md'}", flush=True)


if __name__ == "__main__":
    main()
