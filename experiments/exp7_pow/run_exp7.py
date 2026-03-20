import argparse
import csv
import json
import os
import shlex
import statistics
from pathlib import Path
from typing import Dict, List

from analysis.common_charts import append_tps_vs_tx_by_nodes_chart, parse_bool_flag
from analysis.svg_chart import line_chart_svg
from collector.log_parser import parse_pow_metrics
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner
from controller.param_matrix import build_matrix
from report.exporter import export_markdown, export_pdf


def parse_int_list(value: str) -> List[int]:
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


def build_default_loadgen_args() -> str:
    return (
        "--protocol grpc "
        "--mode sustained "
        "--duration {duration} "
        "--target-tps {target_tps} "
        "--batch-size {batch_size} "
        "--grpc-endpoint http://127.0.0.1:{grpc_port} "
        "--rpc-endpoint tcp://127.0.0.1:{rpc_port} "
        "--keyring-backend test "
        "--keyring-home {data_root}/nodes_{nodes}/node1 "
        "--account-file {data_root}/nodes_{nodes}/accounts.jsonl "
        "--cli-binary {cli_binary} "
        "--send-amount 1 "
        "--fee-amount 1 "
        "--denom stake "
        "--account-count 100 "
        "--initial-nonce 0 "
        "--metrics-interval 100 "
        "--json-interval-ms 100 "
        "--csv-path {data_root}/loadgen.csv "
        "--chain-id {chain_id}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="实验七：PoW 节点扩展性与性能测试")
    parser.add_argument("--nodes", type=str, default="4,8")
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--difficulty", type=int, default=12)
    parser.add_argument("--target-block-ms", type=float, default=12000.0)
    parser.add_argument("--tx-per-block", type=int, default=1000)
    parser.add_argument("--target-tps", type=int, default=200)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--orphan-base-rate", type=float, default=0.01)
    parser.add_argument("--out", type=str, default="experiments/exp7_pow/report")
    parser.add_argument("--loadgen-args", type=str, default=build_default_loadgen_args())
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
    artifact_root.mkdir(parents=True, exist_ok=True)

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    port_offset = int(os.environ.get("PORT_OFFSET", "0"))
    grpc_port = 9090 + port_offset
    rpc_port = 26657 + port_offset
    chain_id = os.environ.get("CHAIN_ID", "hcp-exp7")
    cli_binary_env = os.environ.get("HCPD_BINARY", "hcpd")
    if os.path.isabs(cli_binary_env):
        cli_binary = cli_binary_env
    elif "/" in cli_binary_env or cli_binary_env.startswith("."):
        cli_binary = str((lab_root / cli_binary_env).resolve())
    else:
        cli_binary = cli_binary_env

    node_list = parse_int_list(args.nodes)
    matrix = build_matrix({"nodes": node_list})
    runner = ExperimentRunner(project_root=project_root)
    base_loadgen_args = shlex.split(args.loadgen_args)

    points: List[ExperimentPoint] = []
    for row in matrix:
        node_count = int(row["nodes"])
        for run_idx in range(1, args.repeat + 1):
            data_root = artifact_root / f"nodes_{node_count}" / f"run_{run_idx}" / "data"
            log_root = artifact_root / f"nodes_{node_count}" / f"run_{run_idx}" / "logs"
            data_root.mkdir(parents=True, exist_ok=True)
            log_root.mkdir(parents=True, exist_ok=True)

            os.environ["CONSENSUS_ENGINE"] = "pow"
            os.environ["POW_NODE_COUNT"] = str(node_count)
            os.environ["POW_DIFFICULTY"] = str(args.difficulty)
            os.environ["POW_TARGET_BLOCK_MS"] = str(args.target_block_ms)
            os.environ["POW_TX_PER_BLOCK"] = str(args.tx_per_block)
            os.environ["POW_ORPHAN_BASE_RATE"] = str(args.orphan_base_rate)
            os.environ["INCLUDE_LOOPBACK"] = "true"

            run_matrix = [{"nodes": node_count, "tx": max(args.target_tps * args.duration, args.tx_per_block)}]
            loadgen_args: List[str] = []
            for arg in base_loadgen_args:
                value = (
                    arg.replace("{data_root}", str(data_root))
                    .replace("{nodes}", str(node_count))
                    .replace("{duration}", str(args.duration))
                    .replace("{target_tps}", str(args.target_tps))
                    .replace("{batch_size}", str(args.batch_size))
                    .replace("{cli_binary}", cli_binary)
                    .replace("{grpc_port}", str(grpc_port))
                    .replace("{rpc_port}", str(rpc_port))
                    .replace("{chain_id}", chain_id)
                )
                loadgen_args.append(value)

            print(
                f"实验点: nodes={node_count} run={run_idx} difficulty={args.difficulty} duration={args.duration}s",
                flush=True,
            )
            result = runner.run(
                name="实验七：PoW 节点扩展性与性能测试",
                description="固定单节点单核算力，比较 4/8 节点在固定难度下的性能",
                matrix=run_matrix,
                data_root=data_root,
                log_root=log_root,
                loadgen_args=loadgen_args,
            )
            metrics = dict(result.points[0].metrics) if result.points else {}
            if "tps" not in metrics:
                duration_s = float(metrics.get("duration_s", 0.0))
                tx_total = float(run_matrix[0]["tx"])
                if duration_s > 0:
                    metrics["tps"] = tx_total / duration_s
            log_dir = log_root / f"nodes_{node_count}"
            pow_metrics = parse_pow_metrics(log_dir)
            metrics.update(pow_metrics)
            metrics["pow_cpu_cores_per_node"] = 1.0
            points.append(
                ExperimentPoint(
                    params={
                        "nodes": node_count,
                        "run": run_idx,
                        "duration_s": args.duration,
                        "difficulty": args.difficulty,
                        "tx_per_block": args.tx_per_block,
                    },
                    metrics={k: float(v) for k, v in metrics.items()},
                )
            )

    aggregated: Dict[int, Dict[str, float]] = {}
    aggregated_std: Dict[int, Dict[str, float]] = {}
    nodes_sorted = sorted({int(p.params["nodes"]) for p in points})
    metric_keys = sorted({key for p in points for key in p.metrics.keys()})
    for n in nodes_sorted:
        node_points = [p.metrics for p in points if int(p.params["nodes"]) == n]
        aggregated[n] = {}
        aggregated_std[n] = {}
        for key in metric_keys:
            values = [float(m.get(key, 0.0)) for m in node_points]
            aggregated[n][key] = avg(values)
            aggregated_std[n][key] = stddev(values)

    result_points: List[ExperimentPoint] = []
    for n in nodes_sorted:
        row = {"nodes": float(n)}
        for key, value in aggregated[n].items():
            row[key] = value
            row[f"{key}_std"] = aggregated_std[n][key]
        result_points.append(ExperimentPoint(params={"nodes": n}, metrics=row))
    result = ExperimentResult(
        name="实验七：PoW 节点扩展性与性能测试",
        description="4/8 节点单核 PoW 对比：TPS、延迟、出块间隔与孤块率",
        points=result_points,
        metadata={
            "nodes": nodes_sorted,
            "repeat": args.repeat,
            "duration_s": args.duration,
            "difficulty": args.difficulty,
            "target_block_ms": args.target_block_ms,
            "tx_per_block": args.tx_per_block,
            "target_tps": args.target_tps,
            "cpu_cores_per_node": 1,
        },
    )
    runner.save_result(output_dir / "result.json", result)

    rows: List[Dict[str, float]] = []
    for n in nodes_sorted:
        rows.append(
            {
                "nodes": float(n),
                "tps": float(aggregated[n].get("tps", 0.0)),
                "latency_ms": float(aggregated[n].get("avg_confirm_time_ms", 0.0)),
                "block_interval_ms": float(aggregated[n].get("pow_block_interval_avg_ms", 0.0)),
                "orphan_rate": float(aggregated[n].get("pow_orphan_rate_observed", 0.0)),
                "cpu_percent": float(aggregated[n].get("cpu_percent", 0.0)),
                "pow_hash_attempts": float(aggregated[n].get("pow_hash_attempts_avg", 0.0)),
            }
        )
    csv_path = output_dir / "exp7_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    figures: List[str] = []
    x_nodes = [float(n) for n in nodes_sorted]
    chart_defs = [
        ("pow_tps_vs_nodes.svg", "PoW TPS vs Nodes", "nodes", "tps", [aggregated[n].get("tps", 0.0) for n in nodes_sorted]),
        (
            "pow_latency_vs_nodes.svg",
            "PoW Confirm Latency vs Nodes",
            "nodes",
            "latency_ms",
            [aggregated[n].get("avg_confirm_time_ms", 0.0) for n in nodes_sorted],
        ),
        (
            "pow_block_interval_vs_nodes.svg",
            "PoW Block Interval vs Nodes",
            "nodes",
            "block_interval_ms",
            [aggregated[n].get("pow_block_interval_avg_ms", 0.0) for n in nodes_sorted],
        ),
        (
            "pow_orphan_rate_vs_nodes.svg",
            "PoW Orphan Rate vs Nodes",
            "nodes",
            "orphan_rate",
            [aggregated[n].get("pow_orphan_rate_observed", 0.0) for n in nodes_sorted],
        ),
    ]
    for name, title, x_label, y_label, ys in chart_defs:
        svg = line_chart_svg(x_nodes, [float(v) for v in ys], title, x_label, y_label)
        write_svg(figures_dir / name, svg)
        figures.append(f"figures/{name}")

    chart_points = [
        {"params": {"nodes": n, "tx": args.target_tps * args.duration}, "metrics": {"tps": aggregated[n].get("tps", 0.0)}}
        for n in nodes_sorted
    ]
    append_tps_vs_tx_by_nodes_chart(
        figures=figures,
        points=chart_points,
        output_dir=output_dir,
        figures_dir=figures_dir,
        line_figure_name="exp7_tps_vs_tx_by_nodes.svg",
        bar_figure_name="exp7_tps_vs_tx_by_nodes_bar.svg",
        title="实验7 性能曲线（TPS）",
        line_chart=parse_bool_flag(args.line_chart, True),
        bar_chart=parse_bool_flag(args.bar_chart, True),
    )

    summary = "\n".join(
        [
            "实验七：基于 PoW 算法的节点扩展性与性能测试",
            f"节点规模: {','.join(str(v) for v in nodes_sorted)}",
            f"单节点 CPU: 1 Core",
            f"PoW 难度: {args.difficulty}",
            f"目标出块时间(ms): {args.target_block_ms:.2f}",
            f"每块交易数: {args.tx_per_block}",
            f"持续时长(s): {args.duration}",
            f"目标发送 TPS: {args.target_tps}",
        ]
        + [
            "nodes={nodes} TPS={tps:.2f} latency={latency:.2f}ms block_interval={block:.2f}ms orphan={orphan:.4f} cpu={cpu:.2f}%".format(
                nodes=n,
                tps=float(aggregated[n].get("tps", 0.0)),
                latency=float(aggregated[n].get("avg_confirm_time_ms", 0.0)),
                block=float(aggregated[n].get("pow_block_interval_avg_ms", 0.0)),
                orphan=float(aggregated[n].get("pow_orphan_rate_observed", 0.0)),
                cpu=float(aggregated[n].get("cpu_percent", 0.0)),
            )
            for n in nodes_sorted
        ]
    )

    export_pdf(
        template_path=lab_root / "report" / "template.tex",
        output_dir=output_dir,
        title="实验七报告",
        summary=summary,
        figures=[],
    )
    export_markdown(
        output_dir=output_dir,
        title="实验七报告",
        summary=summary,
        figures=figures,
    )

    summary_json = {
        "nodes": nodes_sorted,
        "repeat": args.repeat,
        "duration_s": args.duration,
        "difficulty": args.difficulty,
        "target_block_ms": args.target_block_ms,
        "tx_per_block": args.tx_per_block,
        "target_tps": args.target_tps,
        "figures": figures,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"实验七报告已生成至: {output_dir}", flush=True)


if __name__ == "__main__":
    main()
