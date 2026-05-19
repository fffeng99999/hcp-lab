#!/usr/bin/env python3
"""实验6：基于实测数据的性能界限建模。"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import clean_report, save_json, save_md


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "report"
EXP1_SUMMARY = SCRIPT_DIR.parent / "exp1_benchmark" / "report" / "summary.json"
EXP5_SUMMARY = SCRIPT_DIR.parent / "exp5_ablation" / "report" / "summary.json"


def poly2_fit(x, y):
    n = len(x)
    sx = sum(x)
    sx2 = sum(v * v for v in x)
    sx3 = sum(v * v * v for v in x)
    sx4 = sum(v * v * v * v for v in x)
    sy = sum(y)
    sxy = sum(x[i] * y[i] for i in range(n))
    sx2y = sum(x[i] * x[i] * y[i] for i in range(n))
    a = [[sx4, sx3, sx2], [sx3, sx2, sx], [sx2, sx, float(n)]]
    b = [sx2y, sxy, sy]
    det = (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )
    if abs(det) < 1e-10:
        alpha = beta = 0.0
        gamma = sy / n if n else 0.0
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
    y_mean = sy / n if n else 0.0
    ss_tot = sum((v - y_mean) ** 2 for v in y)
    residuals = []
    ss_res = 0.0
    for i, xv in enumerate(x):
        pred = alpha * xv * xv + beta * xv + gamma
        res = y[i] - pred
        residuals.append(res)
        ss_res += res * res
    return {
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        "r2": 1 - ss_res / ss_tot if ss_tot > 0 else 1.0,
        "rmse": math.sqrt(ss_res / n) if n else 0.0,
        "mae": sum(abs(r) for r in residuals) / n if n else 0.0,
    }


def main() -> None:
    clean_report(REPORT_DIR)
    if not EXP1_SUMMARY.exists():
        raise SystemExit("[EXP6] 缺少 EXP1 最终数据，请先运行 exp1_benchmark")
    matrix = json.loads(EXP1_SUMMARY.read_text(encoding="utf-8"))
    ablation = json.loads(EXP5_SUMMARY.read_text(encoding="utf-8")) if EXP5_SUMMARY.exists() else {}

    md12 = [
        "## 表4-12 吞吐量饱和边界",
        "",
        "| 算法 | 8节点TPS | 16节点TPS | 32节点TPS |",
        "|------|----------|-----------|-----------|",
    ]
    for engine, data in matrix.items():
        row = [engine]
        for n in [8, 16, 32]:
            d = data.get(str(n), {})
            row.append(f"{d.get('tps_mean', 0):.2f}±{d.get('tps_std', 0):.2f}")
        md12.append("| " + " | ".join(row) + " |")
    save_md(md12, REPORT_DIR / "table4_12.md")

    fit_summary = {}
    md13 = [
        "## 表4-13 尾延迟退化模型拟合",
        "",
        "| 算法 | α | β | γ | R² | RMSE | MAE |",
        "|------|---|---|---|----|------|-----|",
    ]
    for engine, data in matrix.items():
        xs, ys = [], []
        for n in [8, 16, 32]:
            if str(n) in data:
                xs.append(float(n))
                ys.append(float(data[str(n)].get("p99_mean", 0.0)))
        if len(xs) >= 3:
            fit = poly2_fit(xs, ys)
            fit_summary[engine] = fit
            md13.append(
                f"| {engine} | {fit['alpha']:.4f} | {fit['beta']:.4f} | {fit['gamma']:.2f} | "
                f"{fit['r2']:.4f} | {fit['rmse']:.2f} | {fit['mae']:.2f} |"
            )
    save_md(md13, REPORT_DIR / "table4_13.md")

    md14 = [
        "## 表4-14 统计验证与机制对比",
        "",
        "| 对比 | 指标 | 基线 | 优化组 | 变化 |",
        "|------|------|------|--------|------|",
    ]
    a32 = ablation.get("A_Baseline", {}).get("32", {})
    c32 = ablation.get("C_Hierarchical", {}).get("32", {})
    d32 = ablation.get("D_Lightweight", {}).get("32", {})
    if a32 and c32:
        md14.append(f"| PBFT->分层tPBFT | TPS | {a32['tps_mean']:.2f} | {c32['tps_mean']:.2f} | {(c32['tps_mean']-a32['tps_mean'])/a32['tps_mean']*100:.1f}% |")
        md14.append(f"| PBFT->分层tPBFT | P99 | {a32['p99_mean']:.2f} | {c32['p99_mean']:.2f} | {(c32['p99_mean']-a32['p99_mean'])/a32['p99_mean']*100:.1f}% |")
    if c32 and d32:
        md14.append(f"| 分层->轻量分层 | TPS | {c32['tps_mean']:.2f} | {d32['tps_mean']:.2f} | {(d32['tps_mean']-c32['tps_mean'])/c32['tps_mean']*100:.1f}% |")
        md14.append(f"| 分层->轻量分层 | P99 | {c32['p99_mean']:.2f} | {d32['p99_mean']:.2f} | {(d32['p99_mean']-c32['p99_mean'])/c32['p99_mean']*100:.1f}% |")
    save_md(md14, REPORT_DIR / "table4_14.md")
    save_json({"fit": fit_summary}, REPORT_DIR / "summary.json")
    print("[EXP6] 完成", flush=True)


if __name__ == "__main__":
    main()
