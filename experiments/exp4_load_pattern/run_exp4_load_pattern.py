#!/usr/bin/env python3
"""Experiment 4: Uniform vs Zipf load-pattern sensitivity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import (
    aggregate_runs,
    clean_report,
    ensure_dirs,
    env_float,
    env_int,
    env_list_str,
    run_engine_loadgen_point,
    save_json,
    save_md,
    stage_binaries,
)


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "report"
EXP_NAME = "exp4_load_pattern"

DEFAULT_ENGINES = ["pbft", "hotstuff", "raft", "cometbft-light", "tpbft"]
ENGINE_LABELS = {
    "pbft": "PBFT",
    "hotstuff": "HotStuff",
    "raft": "Raft",
    "cometbft-light": "CometBFT-light",
    "tpbft": "tPBFT",
}


def fmt(mean_key: str, std_key: str, data: dict) -> str:
    return f"{data.get(mean_key, 0.0):.2f}±{data.get(std_key, 0.0):.2f}"


def zipf_tps_delta(uniform_tps: float, zipf_tps: float) -> float:
    if uniform_tps <= 0:
        return 0.0
    return (zipf_tps - uniform_tps) / uniform_tps * 100.0


def impact_label(delta_tps: float, p99_ms: float) -> str:
    if abs(delta_tps) <= 10.0 and p99_ms <= 1000.0:
        return "影响不明显"
    if delta_tps > 10.0:
        return "吞吐提升"
    if p99_ms <= 1000.0:
        return "轻微负面影响"
    return "明显负面影响"


def main() -> None:
    clean_report(REPORT_DIR)
    paths = ensure_dirs(EXP_NAME, REPORT_DIR)
    binaries = stage_binaries(paths)

    engines = env_list_str("EXP4_LOAD_ENGINES", DEFAULT_ENGINES)
    nodes = env_int("EXP4_LOAD_NODES", 16)
    tx_count = env_int("EXP4_LOAD_TXS", 1000)
    repeat = env_int("EXP_REPEAT", env_int("EXP4_LOAD_REPEAT", 5))
    target_tps = env_int("EXP4_LOAD_TARGET_TPS", 10000)
    zipf_alpha = env_float("EXP4_LOAD_ZIPF_ALPHA", 1.2)

    print(
        f"[EXP4-LOAD] modes=uniform,zipf nodes={nodes} tx={tx_count} repeat={repeat} zipf_alpha={zipf_alpha}",
        flush=True,
    )
    results: dict[str, dict[str, dict]] = {}
    modes = [
        ("uniform", "random", None),
        ("zipf", "zipf", zipf_alpha),
    ]
    for engine in engines:
        results[engine] = {}
        for mode_label, account_mode, alpha in modes:
            runs = []
            for r in range(1, repeat + 1):
                point = f"{engine}_n{nodes}_{mode_label}_t{tx_count}_r{r}"
                print(f"  {point}", flush=True)
                runs.append(
                    run_engine_loadgen_point(
                        EXP_NAME,
                        REPORT_DIR,
                        point,
                        engine,
                        nodes,
                        tx_count,
                        target_tps=target_tps,
                        loadgen_mode="fixed",
                        account_selection_mode=account_mode,
                        zipf_alpha=alpha,
                        binaries=binaries,
                        paths=paths,
                    )
                )
            results[engine][mode_label] = aggregate_runs(runs)

    save_json(results, REPORT_DIR / "summary.json")

    md = [
        "## 表3-3 Uniform与Zipf负载模式敏感性对比",
        "",
        f"固定配置：N={nodes}，tx={tx_count}，target_tps={target_tps}，Zipf alpha={zipf_alpha}，每组重复{repeat}次。",
        "",
        "| 算法 | 负载模式D | TPS(tx/s) | P50(ms) | P95(ms) | P99(ms) | 成功率 | ΔTPS_zipf(%) | 影响判断 |",
        "|------|-----------|-----------|---------|---------|---------|--------|-----------|------------|",
    ]
    for engine in engines:
        uniform = results.get(engine, {}).get("uniform", {})
        zipf = results.get(engine, {}).get("zipf", {})
        uniform_tps = float(uniform.get("tps_mean", 0.0))
        for mode_label, data in [("Uniform", uniform), ("Zipf", zipf)]:
            delta_tps = 0.0 if mode_label == "Uniform" else zipf_tps_delta(uniform_tps, float(data.get("tps_mean", 0.0)))
            label = "基准" if mode_label == "Uniform" else impact_label(delta_tps, float(data.get("p99_mean", 0.0)))
            signed_delta = f"{delta_tps:+.2f}%" if mode_label == "Zipf" else "0.00%"
            md.append(
                f"| {ENGINE_LABELS.get(engine, engine)} | {mode_label} | "
                f"{fmt('tps_mean', 'tps_std', data)} | {fmt('p50_mean', 'p50_std', data)} | "
                f"{fmt('p95_mean', 'p95_std', data)} | {fmt('p99_mean', 'p99_std', data)} | "
                f"{data.get('success_rate_mean', 0.0):.3f} | {signed_delta} | {label} |"
            )
    save_md(md, REPORT_DIR / "table3_3.md")
    print(f"[EXP4-LOAD] wrote {REPORT_DIR / 'table3_3.md'}", flush=True)


if __name__ == "__main__":
    main()
