#!/usr/bin/env python3
"""Extended node-scale samples for Section 3.7 fitting only.

Runs the light engine baseline matrix at 12 node counts:
8,16,24,32,40,48,56,64,72,80,88,96.
No ablation, no group scan, no saturation scan, no official CometBFT.
"""
import argparse
import math
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
EXP_NAME = "exp7_extended_fit"
DEFAULT_NODES = [8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88, 96]
DEFAULT_ENGINES = ["pbft", "hotstuff", "raft", "cometbft-light", "tpbft"]
ENGINE_LABELS = {
    "pbft": "PBFT",
    "hotstuff": "HotStuff",
    "raft": "Raft",
    "cometbft-light": "CometBFT-light",
    "tpbft": "tPBFT",
}
ENGINE_ALIASES = {
    "pbft": "pbft",
    "hotstuff": "hotstuff",
    "hot": "hotstuff",
    "raft": "raft",
    "cometbft-light": "cometbft-light",
    "cometbft_light": "cometbft-light",
    "comet-light": "cometbft-light",
    "tpbft": "tpbft",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run extended fitting samples for Section 3.7.")
    parser.add_argument("engines", nargs="*", help="Optional engines, space/comma separated.")
    parser.add_argument("--render-only", action="store_true", help="Render tables from existing summary.json without rerunning.")
    return parser.parse_args()


def selected_engines(args: argparse.Namespace) -> list[str]:
    if not args.engines:
        return list(DEFAULT_ENGINES)
    chosen: list[str] = []
    for arg in args.engines:
        for raw in arg.split(","):
            key = raw.strip().lower()
            if not key:
                continue
            if key not in ENGINE_ALIASES:
                raise SystemExit(f"Unknown engine '{raw}'. Allowed: {', '.join(DEFAULT_ENGINES)}")
            value = ENGINE_ALIASES[key]
            if value not in chosen:
                chosen.append(value)
    return chosen


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def r2_score(actual: list[float], pred: list[float]) -> float:
    y_bar = avg(actual)
    ss_tot = sum((v - y_bar) ** 2 for v in actual)
    ss_res = sum((actual[i] - pred[i]) ** 2 for i in range(len(actual)))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0


def linear_fit(xs: list[float], ys: list[float]) -> dict:
    x_bar = avg(xs)
    y_bar = avg(ys)
    denom = sum((x - x_bar) ** 2 for x in xs)
    slope = sum((xs[i] - x_bar) * (ys[i] - y_bar) for i in range(len(xs))) / denom if denom else 0.0
    intercept = y_bar - slope * x_bar
    pred = [intercept + slope * x for x in xs]
    return {"intercept": intercept, "slope": slope, "r2": r2_score(ys, pred)}


def poly2_fit(xs: list[float], ys: list[float]) -> dict:
    n = len(xs)
    sx = sum(xs)
    sx2 = sum(x * x for x in xs)
    sx3 = sum(x * x * x for x in xs)
    sx4 = sum(x * x * x * x for x in xs)
    sy = sum(ys)
    sxy = sum(xs[i] * ys[i] for i in range(n))
    sx2y = sum(xs[i] * xs[i] * ys[i] for i in range(n))
    a = [[sx4, sx3, sx2], [sx3, sx2, sx], [sx2, sx, float(n)]]
    b = [sx2y, sxy, sy]
    det = (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )
    if abs(det) < 1e-10:
        alpha = beta = 0.0
        gamma = avg(ys)
    else:
        alpha = (
            b[0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
            - a[0][1] * (b[1] * a[2][2] - a[1][2] * b[2])
            + a[0][2] * (b[1] * a[2][1] - a[1][1] * b[2])
        ) / det
        beta = (
            a[0][0] * (b[1] * a[2][2] - a[1][2] * b[2])
            - b[0] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
            + a[0][2] * (a[1][0] * b[2] - b[1] * a[2][0])
        ) / det
        gamma = (
            a[0][0] * (a[1][1] * b[2] - b[1] * a[2][1])
            - a[0][1] * (a[1][0] * b[2] - b[1] * a[2][0])
            + b[0] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
        ) / det
    pred = [alpha * x * x + beta * x + gamma for x in xs]
    return {"alpha": alpha, "beta": beta, "gamma": gamma, "r2": r2_score(ys, pred)}


def p99_limit_n(fit: dict, limit: float = 2000.0) -> str:
    a = fit["alpha"]
    b = fit["beta"]
    c = fit["gamma"] - limit
    if abs(a) < 1e-9:
        if abs(b) < 1e-9:
            return "阈值外"
        n = -c / b
        return f"{n:.0f}" if n > 0 else "阈值外"
    disc = b * b - 4 * a * c
    if disc < 0:
        return "阈值外"
    roots = [(-b + math.sqrt(disc)) / (2 * a), (-b - math.sqrt(disc)) / (2 * a)]
    positive = [r for r in roots if r > 0]
    return f"{min(positive):.0f}" if positive else "阈值外"


def fmt(data: dict, key: str) -> str:
    return f"{float(data.get(key, 0.0)):.2f}"


def main() -> None:
    args = parse_args()
    engines = selected_engines(args)

    nodes_list = env_list_int("EXP7_NODES", DEFAULT_NODES)
    tx_count = env_int("EXP7_TXS", 1000)
    repeat = env_int("EXP_REPEAT", env_int("EXP7_REPEAT", 10))

    if args.render_only:
        matrix = __import__("json").loads((REPORT_DIR / "summary.json").read_text(encoding="utf-8"))
    else:
        clean_report(REPORT_DIR)
        paths = ensure_dirs(EXP_NAME, REPORT_DIR)
        binaries = stage_binaries(paths)
        print(f"[EXP7] extended fit engines={','.join(engines)} nodes={nodes_list} repeat={repeat}", flush=True)
        matrix: dict[str, dict[str, dict]] = {}
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
        "## 扩展实验：3.7节拟合采样矩阵",
        "",
        f"统一负载：Uniform，tx={tx_count}，节点采样N={','.join(map(str, nodes_list))}，每点重复{repeat}次。",
        "",
        "| 算法 | N | TPS(tx/s) | P50(ms) | P95(ms) | P99(ms) | 成功率 |",
        "|------|---|-----------|---------|---------|---------|--------|",
    ]
    for engine in engines:
        for nodes in nodes_list:
            d = matrix[engine][str(nodes)]
            md.append(
                f"| {ENGINE_LABELS[engine]} | {nodes} | {fmt(d, 'tps_mean')} | {fmt(d, 'p50_mean')} | "
                f"{fmt(d, 'p95_mean')} | {fmt(d, 'p99_mean')} | {float(d.get('success_rate_mean', 0.0)):.3f} |"
            )
    save_md(md, REPORT_DIR / "table3_7_ext_matrix.md")

    fit_summary = {"throughput": {}, "p99": {}}
    table_tps = [
        "## 扩展实验：吞吐量边界拟合",
        "",
        "| 算法 | N=8 Tsat | N=16 Tsat | N=32 Tsat | 拟合模型 | R^2 |",
        "|------|----------|-----------|-----------|----------|-----|",
    ]
    table_p99 = [
        "## 扩展实验：尾延迟退化模型拟合",
        "",
        "| 算法 | 采样点数 | alpha | beta | gamma | R^2 | N*（P99=2000ms） |",
        "|------|----------|-------|------|-------|-----|-------------------|",
    ]
    for engine in engines:
        xs = [float(n) for n in nodes_list if str(n) in matrix[engine]]
        tps = [float(matrix[engine][str(n)].get("tps_mean", 0.0)) for n in nodes_list if str(n) in matrix[engine]]
        p99 = [float(matrix[engine][str(n)].get("p99_mean", 0.0)) for n in nodes_list if str(n) in matrix[engine]]
        lf = linear_fit(xs, tps)
        pf = poly2_fit(xs, p99)
        fit_summary["throughput"][engine] = lf
        fit_summary["p99"][engine] = pf
        sign = "-" if lf["slope"] < 0 else "+"
        table_tps.append(
            f"| {ENGINE_LABELS[engine]} | {float(matrix[engine]['8'].get('tps_mean', 0.0)):.2f} | "
            f"{float(matrix[engine]['16'].get('tps_mean', 0.0)):.2f} | "
            f"{float(matrix[engine]['32'].get('tps_mean', 0.0)):.2f} | "
            f"T_sat(N) = {lf['intercept']:.2f} {sign} {abs(lf['slope']):.2f}N | {lf['r2']:.4f} |"
        )
        table_p99.append(
            f"| {ENGINE_LABELS[engine]} | {len(xs)} | {pf['alpha']:.4f} | {pf['beta']:.4f} | "
            f"{pf['gamma']:.2f} | {pf['r2']:.4f} | {p99_limit_n(pf)} |"
        )
    save_json(fit_summary, REPORT_DIR / "fit_summary.json")
    save_md(table_tps, REPORT_DIR / "table3_15_ext.md")
    save_md(table_p99, REPORT_DIR / "table3_16_ext.md")
    print(f"[EXP7] wrote {REPORT_DIR}", flush=True)


if __name__ == "__main__":
    main()
