import argparse
import csv
import json
import math
import os
import random
import shlex
import statistics
from pathlib import Path
from typing import Dict, List, Tuple

from analysis.common_charts import append_tps_vs_tx_by_nodes_chart, parse_bool_flag
from analysis.svg_chart import line_chart_svg
from collector.log_parser import parse_hierarchical_metrics
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner


def parse_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stddev(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return statistics.stdev(values)


def write_svg(path: Path, content: str) -> None:
    if not content:
        return
    path.write_text(content, encoding="utf-8")


def compute_r2(actual: List[float], predicted: List[float]) -> float:
    if not actual or len(actual) != len(predicted):
        return 0.0
    mean_actual = avg(actual)
    ss_tot = sum((x - mean_actual) ** 2 for x in actual)
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, predicted))
    if ss_tot == 0:
        return 0.0
    return 1 - ss_res / ss_tot


def comm_theory(n: int, g: int, msg_bytes: int) -> float:
    if g <= 0:
        return 0.0
    return (n * n / g + g * g) * msg_bytes


def simulate_fail_rate(p: float, g: int, s: int, trials: int) -> float:
    if g <= 0 or s <= 0 or trials <= 0:
        return 0.0
    failures = 0
    for _ in range(trials):
        failed = False
        for _ in range(g):
            all_bad = True
            for _ in range(s):
                if random.random() >= p:
                    all_bad = False
                    break
            if all_bad:
                failed = True
                break
        if failed:
            failures += 1
    return failures / trials


def main() -> None:
    parser = argparse.ArgumentParser(description="实验四：分层共识通信复杂度与高频负载边界")
    parser.add_argument("--groups", type=str, default="32,16,8,4,2")
    parser.add_argument("--nodes", type=int, default=32)
    parser.add_argument("--tx", type=int, default=10000)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--out", type=str, default="experiments/exp4_hierarchical_consensus/report")
    parser.add_argument("--message-bytes", type=int, default=256)
    parser.add_argument("--base-latency-ms", type=float, default=1.0)
    parser.add_argument("--phase-weight-inner", type=float, default=1.0)
    parser.add_argument("--phase-weight-outer", type=float, default=1.0)
    parser.add_argument("--loadgen-args", type=str, default="")
    parser.add_argument("--line-chart", type=str, default="true")
    parser.add_argument("--bar-chart", type=str, default="true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[3]
    lab_root = project_root / "hcp-lab"
    out_path = Path(args.out)
    if not out_path.is_absolute():
        if out_path.parts and out_path.parts[0] == "hcp-lab":
            out_path = Path(*out_path.parts[1:])
        output_dir = lab_root / out_path
    else:
        output_dir = out_path
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_override = os.environ.get("EXP_ARTIFACT_ROOT")
    if artifact_override:
        artifact_path = Path(artifact_override)
        artifact_root = artifact_path if artifact_path.is_absolute() else project_root / artifact_path
    else:
        artifact_root = output_dir / "artifacts"
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    groups = parse_list(args.groups)
    runner = ExperimentRunner(project_root=project_root)
    base_loadgen_args = shlex.split(args.loadgen_args)

    print(
        "实验四参数: nodes={nodes} tx={tx} groups={groups} repeat={repeat} message_bytes={msg} base_latency_ms={base} phase_inner={inner} phase_outer={outer}".format(
            nodes=args.nodes,
            tx=args.tx,
            groups=",".join(str(g) for g in groups),
            repeat=args.repeat,
            msg=args.message_bytes,
            base=args.base_latency_ms,
            inner=args.phase_weight_inner,
            outer=args.phase_weight_outer,
        ),
        flush=True,
    )
    print(f"实验输出目录: {output_dir}", flush=True)
    print(f"实验数据目录: {artifact_root}", flush=True)

    aggregated: Dict[int, Dict[str, float]] = {}
    aggregated_std: Dict[int, Dict[str, float]] = {}
    points: List[ExperimentPoint] = []

    for g in groups:
        if g <= 0 or args.nodes % g != 0:
            continue
        s = args.nodes // g
        samples: List[Dict[str, float]] = []
        for repeat_idx in range(1, args.repeat + 1):
            data_root = artifact_root / f"g_{g}" / f"run_{repeat_idx}" / "data"
            log_root = artifact_root / f"g_{g}" / f"run_{repeat_idx}" / "logs"
            data_root.mkdir(parents=True, exist_ok=True)
            log_root.mkdir(parents=True, exist_ok=True)

            os.environ["CONSENSUS_ENGINE"] = "hierarchical"
            os.environ["HIERARCHICAL_GROUP_COUNT"] = str(g)
            os.environ["HIERARCHICAL_GROUP_SIZE"] = str(s)
            os.environ["HIERARCHICAL_NODE_COUNT"] = str(args.nodes)
            os.environ["HIERARCHICAL_MESSAGE_BYTES"] = str(args.message_bytes)
            os.environ["HIERARCHICAL_BASE_LATENCY_MS"] = str(args.base_latency_ms)
            os.environ["HIERARCHICAL_PHASE_WEIGHT_INNER"] = str(args.phase_weight_inner)
            os.environ["HIERARCHICAL_PHASE_WEIGHT_OUTER"] = str(args.phase_weight_outer)
            os.environ["INCLUDE_LOOPBACK"] = "true"

            matrix = [{"nodes": args.nodes, "tx": args.tx}]
            loadgen_args = [arg.replace("{data_root}", str(data_root)) for arg in base_loadgen_args]
            print(
                "实验点参数: g={g} s={s} run={run} data_root={data_root} log_root={log_root}".format(
                    g=g,
                    s=s,
                    run=repeat_idx,
                    data_root=data_root,
                    log_root=log_root,
                ),
                flush=True,
            )
            if loadgen_args:
                expanded_preview: List[str] = []
                for arg in loadgen_args:
                    value = arg.replace("{nodes}", str(args.nodes)).replace("{tx}", str(args.tx))
                    expanded_preview.append(value)
                print("负载参数(展开预览): " + " ".join(expanded_preview), flush=True)
            result = runner.run(
                name="实验四：分层共识通信复杂度",
                description="分层共识通信复杂度与高频负载边界评估",
                matrix=matrix,
                data_root=data_root,
                log_root=log_root,
                loadgen_args=loadgen_args,
            )
            metrics = result.points[0].metrics if result.points else {}
            log_dir = log_root / f"nodes_{args.nodes}"
            hierarchy = parse_hierarchical_metrics(log_dir)
            pre_prepare = avg(hierarchy.get("pre_prepare_ms", []))
            prepare = avg(hierarchy.get("prepare_ms", []))
            commit = avg(hierarchy.get("commit_ms", []))
            comm_bytes = avg(hierarchy.get("comm_bytes", []))
            duration_s = float(metrics.get("duration_s", 0.0))
            net_mbps = float(metrics.get("net_mbps", 0.0))
            net_bytes_total = net_mbps * 1024.0 * 1024.0 / 8.0 * duration_s if duration_s > 0 else 0.0

            sample = dict(metrics)
            sample["pre_prepare_ms"] = pre_prepare
            sample["prepare_ms"] = prepare
            sample["commit_ms"] = commit
            sample["comm_bytes_per_block"] = comm_bytes
            sample["net_bytes_total"] = net_bytes_total
            samples.append(sample)

        if not samples:
            continue
        agg: Dict[str, float] = {}
        agg_std: Dict[str, float] = {}
        keys = samples[0].keys()
        for key in keys:
            values = [float(s.get(key, 0.0)) for s in samples]
            agg[key] = avg(values)
            agg_std[key] = stddev(values)
        aggregated[g] = agg
        aggregated_std[g] = agg_std
        points.append(
            ExperimentPoint(
                params={"g": g, "s": s, "nodes": args.nodes, "tx": args.tx},
                metrics=agg,
            )
        )

    result = ExperimentResult(
        name="实验四：分层共识通信复杂度与高频负载边界",
        description="验证分层共识通信复杂度与高频负载性能边界",
        points=points,
        metadata={
            "groups": groups,
            "nodes": args.nodes,
            "tx": args.tx,
            "repeat": args.repeat,
            "message_bytes": args.message_bytes,
        },
    )
    result_path = output_dir / "result.json"
    runner.save_result(result_path, result)

    rows = []
    for g in sorted(aggregated.keys()):
        s = args.nodes // g
        metrics = aggregated[g]
        stds = aggregated_std[g]
        rows.append(
            {
                "g": g,
                "s": s,
                "tps_avg": metrics.get("tps", 0.0),
                "tps_std": stds.get("tps", 0.0),
                "avg_latency_avg": metrics.get("avg_confirm_time_ms", 0.0),
                "avg_latency_std": stds.get("avg_confirm_time_ms", 0.0),
                "p99_avg": metrics.get("p99_ms", 0.0),
                "p99_std": stds.get("p99_ms", 0.0),
                "comm_bytes_avg": metrics.get("comm_bytes_per_block", 0.0),
                "comm_bytes_std": stds.get("comm_bytes_per_block", 0.0),
                "pre_prepare_avg": metrics.get("pre_prepare_ms", 0.0),
                "prepare_avg": metrics.get("prepare_ms", 0.0),
                "commit_avg": metrics.get("commit_ms", 0.0),
                "cpu_avg": metrics.get("cpu_percent", 0.0),
                "net_bytes_total_avg": metrics.get("net_bytes_total", 0.0),
                "consensus_failures_avg": metrics.get("consensus_failures", 0.0),
            }
        )

    csv_path = output_dir / "exp4_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    g_sorted = sorted(aggregated.keys())
    tps_values = [aggregated[g].get("tps", 0.0) for g in g_sorted]
    comm_values = [aggregated[g].get("comm_bytes_per_block", 0.0) for g in g_sorted]
    theory_comm_values = [comm_theory(args.nodes, g, args.message_bytes) for g in g_sorted]
    inv_theory = [1.0 / v if v > 0 else 0.0 for v in theory_comm_values]
    r2_comm = compute_r2(comm_values, theory_comm_values)

    write_svg(
        figures_dir / "tps_vs_g.svg",
        line_chart_svg([float(g) for g in g_sorted], tps_values, "TPS vs g", "g", "TPS"),
    )
    write_svg(
        figures_dir / "comm_vs_g.svg",
        line_chart_svg([float(g) for g in g_sorted], comm_values, "通信量 vs g", "g", "通信量(字节/区块)"),
    )
    write_svg(
        figures_dir / "comm_theory_vs_g.svg",
        line_chart_svg([float(g) for g in g_sorted], theory_comm_values, "理论 C(g) 曲线", "g", "通信量(字节/区块)"),
    )
    write_svg(
        figures_dir / "tps_vs_inv_comm.svg",
        line_chart_svg(inv_theory, tps_values, "TPS 与理论拟合", "1/C(g)", "TPS"),
    )

    p_list = [0.1, 0.2, 0.3]
    safety_rows: List[Dict[str, float]] = []
    for p in p_list:
        for g in g_sorted:
            s = args.nodes // g
            sim = simulate_fail_rate(p, g, s, 1000)
            theory = 1 - (1 - p ** s) ** g
            safety_rows.append(
                {"p": p, "g": g, "s": s, "p_fail_sim": sim, "p_fail_theory": theory}
            )

    safety_csv = output_dir / "exp4_safety.csv"
    with safety_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["p", "g", "s", "p_fail_sim", "p_fail_theory"],
        )
        writer.writeheader()
        writer.writerows(safety_rows)

    for p in p_list:
        p_values = [row for row in safety_rows if row["p"] == p]
        g_vals = [float(row["g"]) for row in p_values]
        sim_vals = [float(row["p_fail_sim"]) for row in p_values]
        write_svg(
            figures_dir / f"safety_sim_p{p}.svg",
            line_chart_svg(g_vals, sim_vals, f"安全概率曲线 p={p}", "g", "P_fail"),
        )

    pareto_x = []
    pareto_y = []
    p_for_pareto = 0.2
    for g in g_sorted:
        s = args.nodes // g
        pfail = 1 - (1 - p_for_pareto ** s) ** g
        pareto_x.append(pfail)
        pareto_y.append(aggregated[g].get("tps", 0.0))
    write_svg(
        figures_dir / "pareto_safety_tps.svg",
        line_chart_svg(pareto_x, pareto_y, "安全-性能 Pareto", "P_fail", "TPS"),
    )
    extra_figures: List[str] = []
    append_tps_vs_tx_by_nodes_chart(
        figures=extra_figures,
        points=points,
        output_dir=output_dir,
        figures_dir=figures_dir,
        line_figure_name="exp4_tps_vs_tx_by_nodes.svg",
        bar_figure_name="exp4_tps_vs_tx_by_nodes_bar.svg",
        title="实验4 性能曲线（TPS）",
        line_chart=parse_bool_flag(args.line_chart, True),
        bar_chart=parse_bool_flag(args.bar_chart, True),
    )

    summary = {
        "g_star": (args.nodes * args.nodes / 2.0) ** (1.0 / 3.0),
        "r2_comm": r2_comm,
        "groups": g_sorted,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
