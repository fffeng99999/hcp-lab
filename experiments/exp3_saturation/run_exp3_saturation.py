#!/usr/bin/env python3
"""Experiment 3: fixed-node load-intensity saturation scan."""
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
EXP_NAME = "exp3_saturation"
DEFAULT_ENGINES = ["pbft", "hotstuff", "raft", "cometbft-light", "tpbft"]
ENGINE_LABELS = {
    "pbft": "PBFT",
    "hotstuff": "HotStuff",
    "raft": "Raft",
    "cometbft-light": "CometBFT-light",
    "tpbft": "tPBFT",
}


def saturation_estimate(by_lambda: dict, lambdas: list[int]) -> str:
    points = [(lam, float(by_lambda.get(str(lam), {}).get("tps_mean", 0.0))) for lam in lambdas]
    max_tps = max((v for _, v in points), default=0.0)
    if max_tps <= 0:
        return "待运行"
    threshold = max_tps * 0.95
    sat_lambda = next((lam for lam, tps in points if tps >= threshold), points[-1][0])
    return f"lambda约{sat_lambda}，T_sat约{max_tps:.2f}"


def main() -> None:
    clean_report(REPORT_DIR)
    paths = ensure_dirs(EXP_NAME, REPORT_DIR)
    binaries = stage_binaries(paths)

    engines = env_list_str("EXP3_ENGINES", DEFAULT_ENGINES)
    nodes = env_int("EXP3_NODES", 16)
    lambdas = env_list_int("EXP3_LAMBDAS", [250, 500, 1000, 1500, 2000, 2500])
    duration = env_int("EXP3_DURATION", 2)
    repeat = env_int("EXP_REPEAT", env_int("EXP3_REPEAT", 3))

    print(f"[EXP3] saturation scan nodes={nodes} repeat={repeat}", flush=True)
    results = {}
    for engine in engines:
        results[engine] = {}
        for lam in lambdas:
            tx_count = env_int("EXP3_TXS_PER_POINT", lam * duration)
            runs = []
            for r in range(1, repeat + 1):
                point = f"{engine}_n{nodes}_lam{lam}_r{r}"
                print(f"  {point}", flush=True)
                runs.append(
                    run_engine_loadgen_point(
                        EXP_NAME,
                        REPORT_DIR,
                        point,
                        engine,
                        nodes,
                        tx_count,
                        lam,
                        binaries=binaries,
                        paths=paths,
                    )
                )
            results[engine][str(lam)] = aggregate_runs(runs)

    save_json(results, REPORT_DIR / "summary.json")

    md = [
        "## 表3-6 共识算法吞吐饱和点扫描",
        "",
        "| 算法\\lambda | " + " | ".join(str(lam) for lam in lambdas) + " | 饱和拐点估计 |",
        "|-------------|" + "|".join(["------"] * len(lambdas)) + "|--------------|",
    ]
    for engine in engines:
        row = [ENGINE_LABELS.get(engine, engine)]
        for lam in lambdas:
            d = results.get(engine, {}).get(str(lam), {})
            row.append(f"{d.get('tps_mean', 0.0):.2f}")
        row.append(saturation_estimate(results.get(engine, {}), lambdas))
        md.append("| " + " | ".join(row) + " |")

    save_md(md, REPORT_DIR / "table3_6.md")
    print(f"[EXP3] wrote {REPORT_DIR / 'table3_6.md'}", flush=True)


if __name__ == "__main__":
    main()
