#!/usr/bin/env python3
"""Experiment 6: build fitted boundary/statistical tables from measured summaries."""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import clean_report, save_json, save_md


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_DIR = SCRIPT_DIR / "report"
EXP1_SUMMARY = SCRIPT_DIR.parent / "exp1_benchmark" / "report" / "summary.json"
EXP2_SUMMARY = SCRIPT_DIR.parent / "exp2_degradation" / "report" / "summary.json"
EXP3_SUMMARY = SCRIPT_DIR.parent / "exp3_saturation" / "report" / "summary.json"
EXP5_SUMMARY = SCRIPT_DIR.parent / "exp5_ablation" / "report" / "summary.json"

ENGINE_ORDER = ["pbft", "hotstuff", "raft", "cometbft-light", "tpbft"]
ENGINE_LABELS = {
    "pbft": "PBFT",
    "hotstuff": "HotStuff",
    "raft": "Raft",
    "cometbft-light": "CometBFT-light",
    "tpbft": "tPBFT",
    "hierarchical_tpbft": "分层tPBFT",
    "hierarchical_lightweight_tpbft": "Raft轻量子层分层方案",
}


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def r2_score(actual: list[float], pred: list[float]) -> float:
    y_bar = mean(actual)
    ss_tot = sum((v - y_bar) ** 2 for v in actual)
    ss_res = sum((actual[i] - pred[i]) ** 2 for i in range(len(actual)))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0


def linear_fit(xs: list[float], ys: list[float]) -> dict:
    x_bar = mean(xs)
    y_bar = mean(ys)
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
        gamma = mean(ys)
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


def get_config(summary: dict, *names: str) -> dict:
    for name in names:
        if name in summary:
            return summary[name]
    return {}


def get_ablation_node(summary: dict, config_names: list[str], nodes: int) -> dict:
    config = get_config(summary, *config_names)
    return config.get(str(nodes), {}) if config else {}


def pick_saturation_point(points: dict) -> dict:
    rows = []
    for lambda_key, metrics in points.items():
        try:
            lambda_value = float(lambda_key)
        except ValueError:
            continue
        rows.append((lambda_value, metrics))
    rows.sort(key=lambda item: item[0])
    if not rows:
        return {}

    max_tps = max(float(metrics.get("tps_mean", 0.0)) for _, metrics in rows)
    threshold = max_tps * 0.95
    chosen_lambda, chosen_metrics = rows[-1]
    for lambda_value, metrics in rows:
        if float(metrics.get("tps_mean", 0.0)) >= threshold:
            chosen_lambda, chosen_metrics = lambda_value, metrics
            break
    return {
        "lambda": chosen_lambda,
        "t_sat": max_tps,
        "l_tail": float(chosen_metrics.get("p99_mean", 0.0)),
        "success_rate": float(chosen_metrics.get("success_rate_mean", 0.0)),
    }


def degradation_percent(left_tps: float, right_tps: float) -> float:
    if left_tps <= 0:
        return 0.0
    return (left_tps - right_tps) / left_tps * 100.0


def boundary_vector_text(t_sat: float, l_tail: float, r_deg: float) -> str:
    return f"{{T_sat={t_sat:.2f}, L_tail={l_tail:.2f}, R_deg={r_deg:.2f}%}}"


def tail_latency_score(l_tail: float) -> float:
    if l_tail <= 200.0:
        return 1.0
    if l_tail >= 2000.0:
        return 0.0
    return (2000.0 - l_tail) / 1800.0


def boundary_score(t_sat: float, max_t_sat: float, l_tail: float, r_deg: float) -> dict:
    s_t = t_sat / max_t_sat if max_t_sat > 0 else 0.0
    s_l = tail_latency_score(l_tail)
    s_r = max(0.0, min(1.0, 1.0 - r_deg / 100.0))
    score = 0.35 * s_t + 0.45 * s_l + 0.20 * s_r
    return {"s_t": s_t, "s_l": s_l, "s_r": s_r, "score": score}


def collect_samples(summary: dict, config: dict, nodes: int, metric_key: str) -> list[float]:
    if not config:
        return []
    raw = config.get(str(nodes), {}).get("raw", [])
    return [float(run.get("metrics", {}).get(metric_key, 0.0)) for run in raw]


def anova_two_groups(left: list[float], right: list[float]) -> dict:
    groups = [left, right]
    all_values = [v for g in groups for v in g]
    if len(left) < 2 or len(right) < 2:
        return {"ss_between": 0.0, "ss_within": 0.0, "f": 0.0, "p": None}
    grand = mean(all_values)
    ss_between = sum(len(g) * (mean(g) - grand) ** 2 for g in groups)
    ss_within = sum(sum((v - mean(g)) ** 2 for v in g) for g in groups)
    df_between = 1
    df_within = len(all_values) - 2
    ms_between = ss_between / df_between
    ms_within = ss_within / df_within if df_within > 0 else 0.0
    f_value = ms_between / ms_within if ms_within > 0 else 0.0
    p_value = None
    try:
        from scipy.stats import f as f_dist  # type: ignore

        p_value = float(f_dist.sf(f_value, df_between, df_within))
    except Exception:
        p_value = f_survival(f_value, df_between, df_within)
    return {"ss_between": ss_between, "ss_within": ss_within, "f": f_value, "p": p_value}


def betacf(a: float, b: float, x: float) -> float:
    max_iter = 200
    eps = 3.0e-12
    fpmin = 1.0e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * betacf(a, b, x) / a
    return 1.0 - bt * betacf(b, a, 1.0 - x) / b


def f_survival(f_value: float, df1: int, df2: int) -> float:
    if f_value <= 0 or df1 <= 0 or df2 <= 0:
        return 1.0
    x = (df1 * f_value) / (df1 * f_value + df2)
    cdf = regularized_beta(x, df1 / 2.0, df2 / 2.0)
    return max(0.0, min(1.0, 1.0 - cdf))


def main() -> None:
    clean_report(REPORT_DIR)
    if not EXP1_SUMMARY.exists():
        raise SystemExit("[EXP6] missing exp1 summary, run exp1_benchmark first")

    matrix = json.loads(EXP1_SUMMARY.read_text(encoding="utf-8"))
    degradation = json.loads(EXP2_SUMMARY.read_text(encoding="utf-8")) if EXP2_SUMMARY.exists() else {}
    saturation = json.loads(EXP3_SUMMARY.read_text(encoding="utf-8")) if EXP3_SUMMARY.exists() else {}
    ablation = json.loads(EXP5_SUMMARY.read_text(encoding="utf-8")) if EXP5_SUMMARY.exists() else {}
    fit_summary = {"throughput": {}, "p99": {}, "anova": {}, "pb_cpbq": {"algorithm": {}, "optimization": {}}}

    table14 = [
        "## 表3-15 吞吐量饱和边界",
        "",
        "采用最小二乘线性模型拟合节点规模与吞吐边界之间的关系：",
        "",
        "T_sat(A,N)=α_A+β_A N",
        "",
        "其中α_A表示算法A在低节点规模下的理论吞吐截距，β_A表示节点规模每增加1时吞吐边界的平均变化率；β_A越小，说明算法随节点扩展的吞吐退化越缓。",
        "",
        "| 算法 | N=8 Tsat | N=16 Tsat | N=32 Tsat | α_A | β_A | 拟合公式 | R^2 |",
        "|------|----------|-----------|-----------|-----|-----|----------|-----|",
    ]
    for engine in ENGINE_ORDER:
        data = matrix.get(engine, {})
        xs, ys = [], []
        row = [ENGINE_LABELS.get(engine, engine)]
        for n in [8, 16, 32]:
            value = float(data.get(str(n), {}).get("tps_mean", 0.0))
            row.append(f"{value:.2f}" if value else "待运行")
            if value:
                xs.append(float(n))
                ys.append(value)
        if len(xs) >= 3:
            fit = linear_fit(xs, ys)
            sign = "-" if fit["slope"] < 0 else "+"
            row.append(f"{fit['intercept']:.2f}")
            row.append(f"{fit['slope']:.2f}")
            row.append(f"T_sat(N) = {fit['intercept']:.2f} {sign} {abs(fit['slope']):.2f}N")
            row.append(f"{fit['r2']:.4f}")
            fit_summary["throughput"][engine] = fit
        else:
            row.extend(["NA", "NA", "待运行", "NA"])
        table14.append("| " + " | ".join(row) + " |")

    save_md(table14, REPORT_DIR / "table3_15.md")

    table15 = [
        "## 表3-16 尾延迟退化模型拟合",
        "",
        "| 算法 | alpha | beta | gamma | R^2 | N*（外推，P99=2000ms） |",
        "|------|-------|------|-------|-----|------------------------|",
    ]
    for engine in ENGINE_ORDER:
        data = matrix.get(engine, {})
        xs, ys = [], []
        for n in [8, 16, 32]:
            value = float(data.get(str(n), {}).get("p99_mean", 0.0))
            if value:
                xs.append(float(n))
                ys.append(value)
        if len(xs) >= 3:
            fit = poly2_fit(xs, ys)
            fit_summary["p99"][engine] = fit
            table15.append(
                f"| {ENGINE_LABELS.get(engine, engine)} | {fit['alpha']:.4f} | {fit['beta']:.4f} | "
                f"{fit['gamma']:.2f} | {fit['r2']:.4f} | {p99_limit_n(fit)} |"
            )
    save_md(table15, REPORT_DIR / "table3_16.md")

    baseline = get_config(ablation, "A", "A_Baseline")
    optimized = get_config(ablation, "C", "C_Hierarchical", "D", "D_Lightweight")
    table16 = [
        "## 表3-17 ANOVA统计验证",
        "",
        "| 指标 | 组间平方和SS | 组内平方和SS | F值 | p值 | 显著性 |",
        "|------|--------------|--------------|-----|-----|--------|",
    ]
    metric_map = [
        ("TPS", "tps"),
        ("P99", "p99_ms"),
        ("通信消息数", "messages"),
    ]
    for label, key in metric_map:
        left = collect_samples(ablation, baseline, 32, key)
        right = collect_samples(ablation, optimized, 32, key)
        stat = anova_two_groups(left, right)
        fit_summary["anova"][label] = stat
        p = stat["p"]
        p_text = f"{p:.3e}" if p is not None else "NA"
        sig = "显著" if p is not None and p < 0.05 else "待统计包计算" if p is None else "不显著"
        table16.append(
            f"| {label} | {stat['ss_between']:.4f} | {stat['ss_within']:.4f} | "
            f"{stat['f']:.4f} | {p_text} | {sig} |"
        )
    save_md(table16, REPORT_DIR / "table3_17.md")

    table17 = [
        "## 表3-18 PB-CPBQ综合评分权重表",
        "",
        "| 指标 | 含义 | 归一化方向 | 权重 |",
        "|------|------|------------|------|",
        "| S_T | 吞吐量饱和能力，来自T_sat | 越大越好 | 0.35 |",
        "| S_L | 尾延迟控制能力，来自L_tail/P99 | 越小越好 | 0.45 |",
        "| S_R | 扩展退化控制能力，来自R_deg | 越小越好 | 0.20 |",
        "",
        "归一化规则：S_T=T_sat/max(T_sat)；L_tail≤200ms时S_L=1，200ms<L_tail≤2000ms时S_L=(2000-L_tail)/1800，L_tail>2000ms时S_L=0；S_R=1-R_deg/100。",
    ]
    save_md(table17, REPORT_DIR / "table3_18.md")

    algorithm_points = {}
    for engine in ENGINE_ORDER:
        point = pick_saturation_point(saturation.get(engine, {}))
        if not point:
            continue
        algorithm_points[engine] = point
    max_algorithm_t_sat = max((point["t_sat"] for point in algorithm_points.values()), default=0.0)

    table18 = [
        "## 表3-19 算法配置维度PB-CPBQ边界向量与综合评分",
        "",
        "| 算法配置A | N | λ取值 | T_sat(A,N)(tx/s) | L_tail(A,N,λ) P99(ms) | R_deg(A,32) | 综合评分S | 边界向量B(A,N,λ) |",
        "|-----------|---|-------|------------------|------------------------|-------------|-----------|------------------|",
    ]
    for engine, point in algorithm_points.items():
        r_deg = float(degradation.get(engine, {}).get("r_deg_percent", 0.0))
        label = ENGINE_LABELS.get(engine, engine)
        score = boundary_score(point["t_sat"], max_algorithm_t_sat, point["l_tail"], r_deg)
        fit_summary["pb_cpbq"]["algorithm"][engine] = {
            "label": label,
            "nodes": 16,
            "lambda": point["lambda"],
            "t_sat": point["t_sat"],
            "l_tail_p99_ms": point["l_tail"],
            "r_deg_percent": r_deg,
            **score,
        }
        table18.append(
            f"| {label} | 16 | {point['lambda']:.0f} | {point['t_sat']:.2f} | "
            f"{point['l_tail']:.2f} | {r_deg:.2f}% | {score['score']:.3f} | "
            f"{boundary_vector_text(point['t_sat'], point['l_tail'], r_deg)} |"
        )
    save_md(table18, REPORT_DIR / "table3_19.md")

    table19 = [
        "## 表3-20 优化组件维度PB-CPBQ边界向量与综合评分",
        "",
        "| 实验组 | 算法配置A | N | 负载条件 | T_sat近似(tx/s) | L_tail P99(ms) | R_deg(16→32) | 综合评分S | 边界向量B(A,N,λ) |",
        "|--------|-----------|---|----------|-----------------|----------------|-------------|-----------|------------------|",
    ]
    ablation_labels = {
        "A": "PBFT基线",
        "B": "tPBFT信任评分",
        "C": "分层tPBFT",
        "D": "Raft轻量子层分层方案",
    }
    optimization_rows = []
    for group, label in ablation_labels.items():
        node16 = get_ablation_node(ablation, [group], 16)
        node32 = get_ablation_node(ablation, [group], 32)
        if not node32:
            continue
        t16 = float(node16.get("tps_mean", 0.0))
        t32 = float(node32.get("tps_mean", 0.0))
        p99 = float(node32.get("p99_mean", 0.0))
        r_deg = degradation_percent(t16, t32)
        optimization_rows.append((group, label, t32, p99, r_deg))
    max_optimization_t_sat = max((row[2] for row in optimization_rows), default=0.0)
    for group, label, t32, p99, r_deg in optimization_rows:
        score = boundary_score(t32, max_optimization_t_sat, p99, r_deg)
        fit_summary["pb_cpbq"]["optimization"][group] = {
            "label": label,
            "nodes": 32,
            "load": "fixed_tx=1000,target_tps=10000",
            "t_sat_approx": t32,
            "l_tail_p99_ms": p99,
            "r_deg_16_to_32_percent": r_deg,
            **score,
        }
        table19.append(
            f"| {group} | {label} | 32 | fixed_tx=1000,target_tps=10000 | {t32:.2f} | "
            f"{p99:.2f} | {r_deg:.2f}% | {score['score']:.3f} | {boundary_vector_text(t32, p99, r_deg)} |"
        )
    save_md(table19, REPORT_DIR / "table3_20.md")

    save_json(fit_summary, REPORT_DIR / "summary.json")
    print(f"[EXP6] wrote tables 3-15 through 3-20 in {REPORT_DIR}", flush=True)


if __name__ == "__main__":
    main()
