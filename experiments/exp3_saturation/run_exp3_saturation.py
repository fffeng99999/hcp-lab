#!/usr/bin/env python3
"""实验3：负载饱和边界扫描。"""
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


def main() -> None:
    clean_report(REPORT_DIR)
    paths = ensure_dirs(EXP_NAME, REPORT_DIR)
    binaries = stage_binaries(paths)

    engines = env_list_str("EXP3_ENGINES", ["pbft", "tpbft", "hotstuff", "raft", "cometbft-light"])
    nodes = env_int("EXP3_NODES", 16)
    lambdas = env_list_int("EXP3_LAMBDAS", [20, 40, 60, 80, 100, 120])
    duration = env_int("EXP3_DURATION", 10)
    repeat = env_int("EXP_REPEAT", env_int("EXP3_REPEAT", 5))

    print(f"[EXP3] 饱和边界扫描 nodes={nodes} repeat={repeat}", flush=True)
    results = {}
    for engine in engines:
        results[engine] = {}
        for lam in lambdas:
            tx_count = lam * duration
            runs = []
            for r in range(1, repeat + 1):
                point = f"{engine}_n{nodes}_lam{lam}_r{r}"
                print(f"  {point}", flush=True)
                runs.append(
                    run_engine_loadgen_point(
                        EXP_NAME, REPORT_DIR, point, engine, nodes, tx_count, lam,
                        binaries=binaries, paths=paths,
                    )
                )
            results[engine][str(lam)] = aggregate_runs(runs)

    save_json(results, REPORT_DIR / "summary.json")
    md = [
        "## 表4-4 饱和边界初探",
        "",
        "| 算法 | " + " | ".join(f"λ={lam}" for lam in lambdas) + " |",
        "|------|" + "|".join(["------"] * len(lambdas)) + "|",
    ]
    for engine in engines:
        row = [engine]
        for lam in lambdas:
            d = results.get(engine, {}).get(str(lam), {})
            row.append(f"{d.get('tps_mean', 0):.2f}±{d.get('tps_std', 0):.2f}")
        md.append("| " + " | ".join(row) + " |")
    save_md(md, REPORT_DIR / "table4_4.md")
    print("[EXP3] 完成", flush=True)


if __name__ == "__main__":
    main()
