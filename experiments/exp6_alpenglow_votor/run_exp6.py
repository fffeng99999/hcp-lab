import argparse
import csv
import json
import os
import shlex
from pathlib import Path
from typing import Dict, List, Tuple

from analysis.common_charts import append_tps_vs_tx_by_nodes_chart, parse_bool_flag
from analysis.svg_chart import multi_line_chart_svg
from collector.log_parser import parse_votor_metrics
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner


def parse_int_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def parse_float_list(value: str) -> List[float]:
    return [float(v.strip()) for v in value.split(",") if v.strip()]


def build_default_loadgen_args() -> str:
    return (
        "--protocol grpc "
        "--mode sustained "
        "--total-txs {tx} "
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


def write_svg(path: Path, content: str) -> None:
    if not content:
        return
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="实验六：Alpenglow Votor 性能验证")
    parser.add_argument("--nodes", type=str, default="4,8,16,32", help="验证节点数量列表")
    parser.add_argument("--tx", type=int, default=100, help="总交易数")
    parser.add_argument("--faulty-ratio", type=str, default="0,0.1,0.2", help="模拟故障节点比例")
    parser.add_argument("--fast-threshold", type=float, default=0.8, help="快速路径阈值 (default: 80%)")
    parser.add_argument("--slow-threshold", type=float, default=0.6, help="慢速路径阈值 (default: 60%)")
    parser.add_argument("--local-timeout-ms", type=int, default=150, help="本地异步超时时间")
    parser.add_argument("--batch-size", type=int, default=200, help="负载每块交易批量")
    parser.add_argument("--loadgen-args", type=str, default=build_default_loadgen_args())
    parser.add_argument("--out", type=str, default="experiments/exp6_alpenglow_votor/report")
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
    chain_id = os.environ.get("CHAIN_ID", "hcp-exp6")
    cli_binary_env = os.environ.get("HCPD_BINARY", "hcpd")
    if os.path.isabs(cli_binary_env):
        cli_binary = cli_binary_env
    elif "/" in cli_binary_env or cli_binary_env.startswith("."):
        cli_binary = str((lab_root / cli_binary_env).resolve())
    else:
        cli_binary = cli_binary_env

    node_list = parse_int_list(args.nodes)
    fault_list = parse_float_list(args.faulty_ratio)
    runner = ExperimentRunner(project_root=project_root)
    base_loadgen_args = shlex.split(args.loadgen_args)

    points: List[ExperimentPoint] = []

    for n in node_list:
        for f_ratio in fault_list:
            data_root = artifact_root / f"n_{n}" / f"f_{f_ratio}" / "data"
            log_root = artifact_root / f"n_{n}" / f"f_{f_ratio}" / "logs"
            data_root.mkdir(parents=True, exist_ok=True)
            log_root.mkdir(parents=True, exist_ok=True)

            os.environ["CONSENSUS_ENGINE"] = "votor"
            os.environ["VOTOR_NODE_COUNT"] = str(n)
            os.environ["VOTOR_FAST_THRESHOLD"] = str(args.fast_threshold)
            os.environ["VOTOR_SLOW_THRESHOLD"] = str(args.slow_threshold)
            os.environ["VOTOR_LOCAL_TIMEOUT_MS"] = str(args.local_timeout_ms)
            os.environ["VOTOR_SIMULATED_FAULT_RATIO"] = str(f_ratio)
            os.environ["INCLUDE_LOOPBACK"] = "true"

            matrix = [{"nodes": n, "tx": args.tx}]
            loadgen_args: List[str] = []
            for arg in base_loadgen_args:
                value = (
                    arg.replace("{data_root}", str(data_root))
                    .replace("{nodes}", str(n))
                    .replace("{tx}", str(args.tx))
                    .replace("{batch_size}", str(args.batch_size))
                    .replace("{cli_binary}", cli_binary)
                    .replace("{grpc_port}", str(grpc_port))
                    .replace("{rpc_port}", str(rpc_port))
                    .replace("{chain_id}", chain_id)
                )
                loadgen_args.append(value)

            print(f"正在运行实验点: 节点={n}, 故障率={f_ratio}", flush=True)
            result = runner.run(
                name="实验六：Alpenglow Votor 性能验证",
                description=f"Votor nodes={n} faulty_ratio={f_ratio}",
                matrix=matrix,
                data_root=data_root,
                log_root=log_root,
                loadgen_args=loadgen_args,
            )
            metrics = result.points[0].metrics if result.points else {}
            if "tps" not in metrics:
                duration_s = float(metrics.get("duration_s", 0.0))
                if duration_s > 0 and args.tx > 0:
                    metrics["tps"] = float(args.tx) / duration_s

            log_dir = log_root / f"nodes_{n}"
            votor_metrics = parse_votor_metrics(log_dir)
            metrics.update(votor_metrics)
            finalize_p99 = float(metrics.get("votor_finalize_p99_ms", 0.0))
            fast_ratio = float(metrics.get("votor_path_fast_ratio", 0.0))
            metrics["votor_fast_finality_ok"] = (
                1.0 if finalize_p99 > 0 and finalize_p99 <= 150 and fast_ratio > 0.0 else 0.0
            )
            points.append(
                ExperimentPoint(
                    params={"nodes": n, "fault_ratio": f_ratio, "tx": args.tx},
                    metrics={k: float(v) for k, v in metrics.items()},
                )
            )

    exp_result = ExperimentResult(
        name="实验六：Alpenglow Votor 性能验证",
        description="验证 Votor Fast/Slow-path 最终性、路径切换与 BLS 聚合收益",
        points=points,
        metadata={
            "nodes": node_list,
            "faulty_ratio": fault_list,
            "tx": args.tx,
            "fast_threshold": args.fast_threshold,
            "slow_threshold": args.slow_threshold,
            "local_timeout_ms": args.local_timeout_ms,
        },
    )
    result_path = output_dir / "result.json"
    runner.save_result(result_path, exp_result)

    save_and_plot(
        output_dir,
        points,
        figures_dir,
        line_chart=parse_bool_flag(args.line_chart, True),
        bar_chart=parse_bool_flag(args.bar_chart, True),
    )
    print(f"实验六报告已生成至: {output_dir}", flush=True)


def save_and_plot(
    output_dir: Path,
    points: List[ExperimentPoint],
    figures_dir: Path,
    line_chart: bool = True,
    bar_chart: bool = True,
) -> None:
    rows: List[Dict[str, float]] = []
    for p in points:
        nodes = float(p.params.get("nodes", 0))
        fault_ratio = float(p.params.get("fault_ratio", 0))
        m = p.metrics
        rows.append(
            {
                "nodes": nodes,
                "fault_ratio": fault_ratio,
                "tps": float(m.get("tps", 0.0)),
                "duration_s": float(m.get("duration_s", 0.0)),
                "finalize_avg_ms": float(m.get("votor_finalize_avg_ms", 0.0)),
                "finalize_p99_ms": float(m.get("votor_finalize_p99_ms", 0.0)),
                "notarize_avg_ms": float(m.get("votor_notarize_avg_ms", 0.0)),
                "notarize_p99_ms": float(m.get("votor_notarize_p99_ms", 0.0)),
                "path_fast_ratio": float(m.get("votor_path_fast_ratio", 0.0)),
                "path_slow_ratio": float(m.get("votor_path_slow_ratio", 0.0)),
                "bls_agg_avg_ms": float(m.get("votor_bls_agg_avg_ms", 0.0)),
                "p2p_vote_bytes_avg": float(m.get("votor_p2p_vote_bytes_avg", 0.0)),
                "gossip_vote_bytes_avg": float(m.get("votor_gossip_vote_bytes_avg", 0.0)),
                "p2p_over_gossip_ratio": float(m.get("votor_p2p_over_gossip_bytes_ratio", 0.0)),
                "fast_finality_ok": float(m.get("votor_fast_finality_ok", 0.0)),
            }
        )

    csv_path = output_dir / "exp6_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    nodes_sorted = sorted({int(p.params.get("nodes", 0)) for p in points})
    faults_sorted = sorted({float(p.params.get("fault_ratio", 0.0)) for p in points})

    def build_grid(key: str) -> Dict[Tuple[int, float], float]:
        grid: Dict[Tuple[int, float], float] = {}
        for p in points:
            n = int(p.params.get("nodes", 0))
            f = float(p.params.get("fault_ratio", 0.0))
            grid[(n, f)] = float(p.metrics.get(key, 0.0))
        return grid

    finalize_p99_grid = build_grid("votor_finalize_p99_ms")
    tps_grid = build_grid("tps")

    x_faults = [float(f) for f in faults_sorted]
    latency_series: List[Tuple[str, List[float]]] = []
    for n in nodes_sorted:
        ys = [finalize_p99_grid.get((n, f), 0.0) for f in faults_sorted]
        latency_series.append((f"n={n}", ys))
    write_svg(
        figures_dir / "latency_vs_fault_ratio.svg",
        multi_line_chart_svg(
            x_faults,
            latency_series,
            "Latency vs Fault Ratio (Finality P99)",
            "fault_ratio",
            "finality_p99_ms",
        ),
    )

    x_nodes = [float(n) for n in nodes_sorted]
    tps_series: List[Tuple[str, List[float]]] = []
    for f in faults_sorted:
        ys = [tps_grid.get((n, f), 0.0) for n in nodes_sorted]
        tps_series.append((f"f={f:.2f}", ys))
    write_svg(
        figures_dir / "tps_vs_validator_count.svg",
        multi_line_chart_svg(
            x_nodes,
            tps_series,
            "TPS vs Validator Count",
            "validators",
            "tps",
        ),
    )
    extra_figures: List[str] = []
    append_tps_vs_tx_by_nodes_chart(
        figures=extra_figures,
        points=points,
        output_dir=output_dir,
        figures_dir=figures_dir,
        line_figure_name="exp6_tps_vs_tx_by_nodes.svg",
        bar_figure_name="exp6_tps_vs_tx_by_nodes_bar.svg",
        title="实验6 性能曲线（TPS）",
        line_chart=line_chart,
        bar_chart=bar_chart,
    )

    summary = {
        "nodes": nodes_sorted,
        "faulty_ratio": faults_sorted,
        "figures": [
            "figures/latency_vs_fault_ratio.svg",
            "figures/tps_vs_validator_count.svg",
        ]
        + extra_figures,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
