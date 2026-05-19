#!/usr/bin/env python3
"""实验1：多共识 engine 基准对比实验。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import (
    aggregate_runs,
    clean_report,
    ensure_dirs,
    env_int,
    env_list_int,
    env_list_str,
    run_engine_loadgen_point,
    save_json,
    save_md,
    stage_binaries,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "report"
EXP_NAME = "exp1_benchmark"


def main() -> None:
    clean_report(REPORT_DIR)
    paths = ensure_dirs(EXP_NAME, REPORT_DIR)
    binaries = stage_binaries(paths)

    engines = env_list_str("EXP1_ENGINES", ["pbft", "tpbft", "hotstuff", "raft", "cometbft"])
    nodes_list = env_list_int("EXP1_NODES", [8, 16, 32])
    tx_count = env_int("EXP1_TXS", 1000)
    target_tps = env_int("EXP1_TARGET_TPS", 100)
    repeat = env_int("EXP_REPEAT", env_int("EXP1_REPEAT", 5))

    print(f"[EXP1] 基准对比开始 repeat={repeat} tx={tx_count} target_tps={target_tps}", flush=True)
    matrix = {}
    for engine in engines:
        matrix[engine] = {}
        for nodes in nodes_list:
            runs = []
            for r in range(1, repeat + 1):
                point = f"{engine}_n{nodes}_t{tx_count}_r{r}"
                print(f"  {point}", flush=True)
                runs.append(
                    run_engine_loadgen_point(
                        EXP_NAME, REPORT_DIR, point, engine, nodes, tx_count, target_tps,
                        binaries=binaries, paths=paths,
                    )
                )
            matrix[engine][str(nodes)] = aggregate_runs(runs)

    save_json(matrix, REPORT_DIR / "summary.json")
    md = [
        "## 表4-2 基准对比实验完整矩阵",
        "",
        "| 算法 | 节点数 | TPS | P99(ms) | 消息数 | 成功率 |",
        "|------|--------|-----|---------|--------|--------|",
    ]
    for engine in engines:
        for nodes in nodes_list:
            d = matrix.get(engine, {}).get(str(nodes), {})
            md.append(
                f"| {engine} | {nodes} | {d.get('tps_mean', 0):.2f}±{d.get('tps_std', 0):.2f} | "
                f"{d.get('p99_mean', 0):.2f}±{d.get('p99_std', 0):.2f} | "
                f"{int(d.get('msgs_mean', 0))}±{int(d.get('msgs_std', 0))} | "
                f"{d.get('success_rate_mean', 0):.3f} |"
            )
    save_md(md, REPORT_DIR / "table4_2.md")
    print("[EXP1] 完成", flush=True)


if __name__ == "__main__":
    main()
