#!/usr/bin/env python3
"""实验4：分层 tPBFT 分组参数扫描。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import (
    clean_report,
    ensure_dirs,
    env_int,
    env_list_int,
    run_engine_loadgen_point,
    save_json,
    save_md,
    stage_binaries,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "report"
EXP_NAME = "exp4_group_scan"


def main() -> None:
    clean_report(REPORT_DIR)
    paths = ensure_dirs(EXP_NAME, REPORT_DIR)
    binaries = stage_binaries(paths)

    nodes = env_int("EXP4_NODES", 32)
    tx_count = env_int("EXP4_TXS", 1000)
    target_tps = env_int("EXP4_TARGET_TPS", 100)
    groups = env_list_int("EXP4_GROUPS", [1, 2, 4, 8, 16])
    results = {}

    print(f"[EXP4] 分组扫描 nodes={nodes} tx={tx_count}", flush=True)
    for g in groups:
        if nodes % g != 0:
            continue
        point = f"hierarchical_tpbft_n{nodes}_g{g}"
        print(f"  {point}", flush=True)
        res = run_engine_loadgen_point(
            EXP_NAME, REPORT_DIR, point, "hierarchical_tpbft", nodes, tx_count, target_tps,
            groups=g, binaries=binaries, paths=paths,
        )
        results[str(g)] = {
            "groups": g,
            "group_size": nodes // g,
            "tps": res["metrics"]["tps"],
            "p99": res["metrics"]["p99_ms"],
            "msgs": res["metrics"]["messages"],
            "bytes": res["metrics"]["bytes"],
            "raw": res,
        }

    save_json(results, REPORT_DIR / "summary.json")
    md5 = [
        "## 表4-5 分组参数扫描",
        "",
        "| K(组数) | M(组大小) | TPS | P99(ms) | 消息数 |",
        "|---------|-----------|-----|---------|--------|",
    ]
    for g in groups:
        d = results.get(str(g))
        if d:
            md5.append(f"| {g} | {d['group_size']} | {d['tps']:.2f} | {d['p99']:.2f} | {int(d['msgs'])} |")
    save_md(md5, REPORT_DIR / "table4_5.md")

    md6 = [
        "## 表4-6 分层复杂度理论验证",
        "",
        "| K | M | 理论消息数 | 实测消息数 | 实测/理论 |",
        "|---|---|------------|------------|-----------|",
    ]
    for g in groups:
        d = results.get(str(g))
        if not d:
            continue
        m = nodes // g
        theory = g * m * (m - 1) * 2 + g * (g - 1) * 2
        ratio = d["msgs"] / theory if theory > 0 else 0
        md6.append(f"| {g} | {m} | {theory} | {int(d['msgs'])} | {ratio:.2f} |")
    save_md(md6, REPORT_DIR / "table4_6.md")
    print("[EXP4] 完成", flush=True)


if __name__ == "__main__":
    main()
