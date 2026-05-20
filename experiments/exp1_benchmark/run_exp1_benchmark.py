#!/usr/bin/env python3
"""Experiment 1: baseline matrix under a uniform fixed-size workload.

Usage:
  python run_exp1_benchmark.py
  python run_exp1_benchmark.py hotstuff
  python run_exp1_benchmark.py pbft raft cometbft
  python run_exp1_benchmark.py pbft,raft,cometbft
"""
import argparse
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
EXP_NAME = "exp1_benchmark"
DEFAULT_ENGINES = ["pbft", "hotstuff", "raft", "cometbft", "tpbft"]
ENGINE_ALIASES = {
    "pbft": "pbft",
    "hotstuff": "hotstuff",
    "hot": "hotstuff",
    "raft": "raft",
    "cometbft": "cometbft",
    "comet": "cometbft",
    "tpbft": "tpbft",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run experiment 1. With no engine arguments, all baseline engines are run.",
    )
    parser.add_argument(
        "engines",
        nargs="*",
        help="Optional engine names, separated by spaces or commas: pbft hotstuff raft cometbft tpbft.",
    )
    return parser.parse_args()


def selected_engines(args: argparse.Namespace) -> list[str]:
    if not args.engines:
        return list(DEFAULT_ENGINES)

    chosen: list[str] = []
    for raw_arg in args.engines:
        for raw_name in raw_arg.split(","):
            name = raw_name.strip().lower()
            if not name:
                continue
            if name not in ENGINE_ALIASES:
                allowed = ", ".join(DEFAULT_ENGINES)
                raise SystemExit(f"Unknown engine '{raw_name}'. Allowed engines: {allowed}")
            canonical = ENGINE_ALIASES[name]
            if canonical not in chosen:
                chosen.append(canonical)
    return chosen


def fmt(mean_key: str, std_key: str, data: dict) -> str:
    return f"{data.get(mean_key, 0):.2f}±{data.get(std_key, 0):.2f}"


def main() -> None:
    args = parse_args()
    engines = selected_engines(args)

    clean_report(REPORT_DIR)
    paths = ensure_dirs(EXP_NAME, REPORT_DIR)
    binaries = stage_binaries(paths)

    nodes_list = env_list_int("EXP1_NODES", [8, 16, 32])
    tx_count = env_int("EXP1_TXS", 1000)
    repeat = env_int("EXP_REPEAT", env_int("EXP1_REPEAT", 5))
    load_mode = "uniform"
    engine_label = ",".join(engines)

    print(
        f"[EXP1] baseline start engines={engine_label} repeat={repeat} "
        f"tx={tx_count} payload≈250B load={load_mode}",
        flush=True,
    )
    matrix = {}
    for engine in engines:
        matrix[engine] = {}
        for nodes in nodes_list:
            runs = []
            for r in range(1, repeat + 1):
                point = f"{engine}_n{nodes}_uniform_t{tx_count}_r{r}"
                print(f"  {point}", flush=True)
                runs.append(
                    run_engine_loadgen_point(
                        EXP_NAME,
                        REPORT_DIR,
                        point,
                        engine,
                        nodes,
                        tx_count,
                        target_tps=None,
                        loadgen_mode="sustained",
                        account_selection_mode="random",
                        binaries=binaries,
                        paths=paths,
                    )
                )
            matrix[engine][str(nodes)] = aggregate_runs(runs)

    save_json(matrix, REPORT_DIR / "summary.json")
    md = [
        "## 表4-2 基准对比实验完整矩阵",
        "",
        f"统一负载：Uniform，tx={tx_count}，约250 bytes/tx。",
        "",
        "| 算法 | 节点数N | TPS(tx/s) | P50(ms) | P95(ms) | P99(ms) | 成功率 |",
        "|------|---------|-----------|---------|---------|---------|--------|",
    ]
    for engine in engines:
        for nodes in nodes_list:
            d = matrix.get(engine, {}).get(str(nodes), {})
            md.append(
                f"| {engine} | {nodes} | {fmt('tps_mean', 'tps_std', d)} | "
                f"{fmt('p50_mean', 'p50_std', d)} | "
                f"{fmt('p95_mean', 'p95_std', d)} | "
                f"{fmt('p99_mean', 'p99_std', d)} | "
                f"{d.get('success_rate_mean', 0):.3f} |"
            )
    save_md(md, REPORT_DIR / "table4_2.md")
    print("[EXP1] done", flush=True)


if __name__ == "__main__":
    main()
