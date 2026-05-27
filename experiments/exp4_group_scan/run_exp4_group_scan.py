#!/usr/bin/env python3
"""Experiment 4: hierarchical tPBFT group-size scan."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import (
    aggregate_runs,
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


def sample_height(run: dict) -> float:
    status = run.get("engine_status", {}).get("sample_status", {})
    height = float(status.get("Height", 0.0))
    return max(height - 1.0, 1.0)


def per_round_messages(summary: dict) -> float:
    raw = summary.get("raw", [])
    if not raw:
        return 0.0
    values = []
    for run in raw:
        msgs = float(run.get("metrics", {}).get("messages", 0.0))
        values.append(msgs / sample_height(run))
    return sum(values) / len(values)


def theoretical_messages(groups: int, group_size: int) -> int:
    # Corrected model: K*M^2 for group broadcasts plus K^2 for inter-group
    # coordination.
    return groups * group_size * group_size + groups * groups


def remark(groups: int) -> str:
    return {
        1: "无分组基线",
        2: "组间协调开销较小",
        4: "默认推荐配置",
        8: "组内规模偏小，协调开销上升",
        16: "组内规模过小，容错余量不足",
    }.get(groups, "待观察")


def main() -> None:
    clean_report(REPORT_DIR)
    paths = ensure_dirs(EXP_NAME, REPORT_DIR)
    binaries = stage_binaries(paths)

    nodes = env_int("EXP4_NODES", 32)
    tx_count = env_int("EXP4_TXS", 1000)
    target_tps = env_int("EXP4_TARGET_TPS", 10000)
    repeat = env_int("EXP_REPEAT", env_int("EXP4_REPEAT", 1))
    groups_list = env_list_int("EXP4_GROUPS", [1, 2, 4, 8, 16])
    results = {}

    print(f"[EXP4] group scan nodes={nodes} tx={tx_count} repeat={repeat}", flush=True)
    for groups in groups_list:
        if nodes % groups != 0:
            print(f"  skip K={groups}: {nodes} is not divisible by K", flush=True)
            continue
        runs = []
        for r in range(1, repeat + 1):
            point = f"hierarchical_tpbft_n{nodes}_g{groups}_r{r}"
            print(f"  {point}", flush=True)
            runs.append(
                run_engine_loadgen_point(
                    EXP_NAME,
                    REPORT_DIR,
                    point,
                    "hierarchical_tpbft",
                    nodes,
                    tx_count,
                    target_tps,
                    groups=groups,
                    binaries=binaries,
                    paths=paths,
                )
            )
        agg = aggregate_runs(runs)
        group_size = nodes // groups
        theory = theoretical_messages(groups, group_size)
        measured = per_round_messages(agg)
        results[str(groups)] = {
            "groups": groups,
            "group_size": group_size,
            "theoretical_messages_per_round": theory,
            "measured_messages_per_round": measured,
            "relative_error_percent": abs(measured - theory) / theory * 100.0 if theory > 0 else 0.0,
            "remark": remark(groups),
            **agg,
        }

    save_json(results, REPORT_DIR / "summary.json")

    table7 = [
        "## 表3-8 分组参数扫描",
        "",
        "| K（分组数） | M=32/K | TPS (tx/s) | P99 (ms) | 实测消息数每轮 | 理论消息数O(KM²+K²) | 备注 |",
        "|-------------|--------|------------|----------|----------------|------------------|------|",
    ]
    for groups in groups_list:
        item = results.get(str(groups))
        if not item:
            continue
        label = f"{groups}（无分组=基线）" if groups == 1 else str(groups)
        table7.append(
            f"| {label} | {item['group_size']} | {item['tps_mean']:.2f} | "
            f"{item['p99_mean']:.2f} | {item['measured_messages_per_round']:.0f} | "
            f"{item['theoretical_messages_per_round']} | {item['remark']} |"
        )
    save_md(table7, REPORT_DIR / "table3_8.md")

    table8 = [
        "## 表3-9 分层复杂度理论验证",
        "",
        "| N | K | M | 理论广播消息数 | 实测广播消息数 | 相对误差 | 验证结论 |",
        "|---|---|---|----------------|----------------|----------|----------|",
    ]
    for groups in groups_list:
        item = results.get(str(groups))
        if not item:
            continue
        if groups == 1:
            conclusion = "未分组基线"
        elif item["relative_error_percent"] <= 8:
            conclusion = "模型基本吻合"
        elif item["relative_error_percent"] <= 25:
            conclusion = "额外协调开销可见"
        else:
            conclusion = "组内规模过小，需单独建模"
        table8.append(
            f"| {nodes} | {groups} | {item['group_size']} | {item['theoretical_messages_per_round']} | "
            f"{item['measured_messages_per_round']:.0f} | {item['relative_error_percent']:.2f}% | {conclusion} |"
        )
    save_md(table8, REPORT_DIR / "table3_9.md")
    print(f"[EXP4] wrote {REPORT_DIR / 'table3_8.md'} and table3_9.md", flush=True)


if __name__ == "__main__":
    main()
