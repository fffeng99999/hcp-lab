import argparse
import csv
import json
import os
import shlex
from pathlib import Path
from typing import Dict, List, Tuple

from analysis.svg_chart import multi_line_chart_svg
from collector.log_parser import parse_ibft_metrics
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner


def parse_int_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def parse_float_list(value: str) -> List[float]:
    return [float(v.strip()) for v in value.split(",") if v.strip()]


def build_default_loadgen_args() -> str:
    return (
        "--protocol grpc "
        "--mode sustained "
        "--target-tps {tps} "
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
    parser = argparse.ArgumentParser(description="实验八：IBFT 性能与 round-change 行为建模")
    parser.add_argument("--nodes", type=str, default="10,20,30,40,50")
    parser.add_argument("--tps", type=str, default="1000,3000,5000")
    parser.add_argument("--tx", type=int, default=5000)
    parser.add_argument("--faulty-ratio", type=str, default="0,0.1,0.2")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--base-latency-ms", type=float, default=1.0)
    parser.add_argument("--jitter-ms", type=float, default=50.0)
    parser.add_argument("--timeout-ms", type=float, default=150.0)
    parser.add_argument("--message-bytes", type=int, default=256)
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--loadgen-args", type=str, default=build_default_loadgen_args())
    parser.add_argument("--out", type=str, default="experiments/exp8_ibft/report")
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
        artifact_root = project_root / "tests" / "exp8_ibft"
    artifact_root.mkdir(parents=True, exist_ok=True)

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    port_offset = int(os.environ.get("PORT_OFFSET", "0"))
    grpc_port = 9090 + port_offset
    rpc_port = 26657 + port_offset
    chain_id = os.environ.get("CHAIN_ID", "hcp-exp8")
    cli_binary_env = os.environ.get("CLI_BINARY", "").strip() or os.environ.get("HCPD_BINARY", "hcpd")
    if os.path.isabs(cli_binary_env):
        cli_binary = cli_binary_env
    elif "/" in cli_binary_env:
        cli_binary = str((project_root / cli_binary_env).resolve())
    else:
        cli_binary = cli_binary_env

    node_list = parse_int_list(args.nodes)
    tps_list = parse_int_list(args.tps)
    fault_list = parse_float_list(args.faulty_ratio)
    runner = ExperimentRunner(project_root=project_root)
    base_loadgen_args = shlex.split(args.loadgen_args)

    points: List[ExperimentPoint] = []

    for n in node_list:
        for tps in tps_list:
            for f_ratio in fault_list:
                data_root = artifact_root / f"n_{n}" / f"tps_{tps}" / f"f_{f_ratio}" / "data"
                log_root = artifact_root / f"n_{n}" / f"tps_{tps}" / f"f_{f_ratio}" / "logs"
                data_root.mkdir(parents=True, exist_ok=True)
                log_root.mkdir(parents=True, exist_ok=True)

                os.environ["CONSENSUS_ENGINE"] = "ibft"
                os.environ["IBFT_NODE_COUNT"] = str(n)
                os.environ["IBFT_FAULTY_RATIO"] = str(f_ratio)
                os.environ["IBFT_BASE_LATENCY_MS"] = str(args.base_latency_ms)
                os.environ["IBFT_JITTER_MS"] = str(args.jitter_ms)
                os.environ["IBFT_TIMEOUT_MS"] = str(args.timeout_ms)
                os.environ["IBFT_MESSAGE_BYTES"] = str(args.message_bytes)
                os.environ["IBFT_MAX_ROUNDS"] = str(args.max_rounds)
                os.environ["INCLUDE_LOOPBACK"] = "true"

                matrix = [{"nodes": n, "tx": args.tx, "tps": tps}]
                loadgen_args: List[str] = []
                for arg in base_loadgen_args:
                    value = (
                        arg.replace("{data_root}", str(data_root))
                        .replace("{nodes}", str(n))
                        .replace("{tx}", str(args.tx))
                        .replace("{tps}", str(tps))
                        .replace("{batch_size}", str(args.batch_size))
                        .replace("{cli_binary}", cli_binary)
                        .replace("{grpc_port}", str(grpc_port))
                        .replace("{rpc_port}", str(rpc_port))
                        .replace("{chain_id}", chain_id)
                    )
                    loadgen_args.append(value)

                print(
                    f"正在运行实验点: 节点={n}, target_tps={tps}, 故障率={f_ratio}",
                    flush=True,
                )
                result = runner.run(
                    name="实验八：IBFT 性能建模",
                    description=f"IBFT nodes={n} tps={tps} faulty_ratio={f_ratio}",
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
                metrics.update(parse_ibft_metrics(log_dir))
                points.append(
                    ExperimentPoint(
                        params={"nodes": n, "tps": tps, "fault_ratio": f_ratio, "tx": args.tx},
                        metrics={k: float(v) for k, v in metrics.items()},
                    )
                )

    exp_result = ExperimentResult(
        name="实验八：IBFT 性能建模",
        description="IBFT 三阶段共识与 round-change 行为的性能边界评估",
        points=points,
        metadata={
            "nodes": node_list,
            "target_tps": tps_list,
            "faulty_ratio": fault_list,
            "tx": args.tx,
            "batch_size": args.batch_size,
            "base_latency_ms": args.base_latency_ms,
            "jitter_ms": args.jitter_ms,
            "timeout_ms": args.timeout_ms,
        },
    )
    result_path = output_dir / "result.json"
    runner.save_result(result_path, exp_result)

    write_outputs(output_dir, figures_dir, points)
    print(f"实验八报告已生成至: {output_dir}", flush=True)


def write_outputs(output_dir: Path, figures_dir: Path, points: List[ExperimentPoint]) -> None:
    rows: List[Dict[str, float]] = []
    for p in points:
        nodes = float(p.params.get("nodes", 0))
        tps = float(p.params.get("tps", 0))
        fault_ratio = float(p.params.get("fault_ratio", 0))
        m = p.metrics
        rows.append(
            {
                "nodes": nodes,
                "target_tps": tps,
                "fault_ratio": fault_ratio,
                "tx": float(p.params.get("tx", 0)),
                "tps": float(m.get("tps", 0.0)),
                "p99_ms": float(m.get("p99_ms", 0.0)),
                "avg_confirm_time_ms": float(m.get("avg_confirm_time_ms", 0.0)),
                "ibft_block_avg_ms": float(m.get("ibft_block_avg_ms", 0.0)),
                "ibft_block_p99_ms": float(m.get("ibft_block_p99_ms", 0.0)),
                "ibft_round_changes_avg": float(m.get("ibft_round_changes_avg", 0.0)),
                "ibft_total_messages_avg": float(m.get("ibft_total_messages_avg", 0.0)),
                "ibft_comm_bytes_avg": float(m.get("ibft_comm_bytes_avg", 0.0)),
            }
        )

    csv_path = output_dir / "exp8_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    if not points:
        return

    nodes_sorted = sorted({int(p.params.get("nodes", 0)) for p in points if int(p.params.get("nodes", 0)) > 0})
    tps_sorted = sorted({int(p.params.get("tps", 0)) for p in points if int(p.params.get("tps", 0)) > 0})
    faults_sorted = sorted({float(p.params.get("fault_ratio", 0.0)) for p in points})
    fault_focus = faults_sorted[0] if faults_sorted else 0.0

    tps_by_nodes: Dict[Tuple[int, int], float] = {}
    p99_by_load: Dict[Tuple[int, int], float] = {}
    for p in points:
        n = int(p.params.get("nodes", 0))
        t = int(p.params.get("tps", 0))
        f = float(p.params.get("fault_ratio", 0.0))
        if f != fault_focus:
            continue
        tps_by_nodes[(n, t)] = float(p.metrics.get("tps", 0.0))
        p99_by_load[(n, t)] = float(p.metrics.get("p99_ms", 0.0))

    x_nodes = [float(n) for n in nodes_sorted]
    series_tps: List[Tuple[str, List[float]]] = []
    for t in tps_sorted:
        ys = [tps_by_nodes.get((n, t), 0.0) for n in nodes_sorted]
        series_tps.append((f"target_tps={t}", ys))
    write_svg(
        figures_dir / "tps_vs_nodes.svg",
        multi_line_chart_svg(x_nodes, series_tps, "TPS vs 节点数", "节点数", "TPS"),
    )

    x_tps = [float(t) for t in tps_sorted]
    series_p99: List[Tuple[str, List[float]]] = []
    for n in nodes_sorted:
        ys = [p99_by_load.get((n, t), 0.0) for t in tps_sorted]
        series_p99.append((f"nodes={n}", ys))
    write_svg(
        figures_dir / "p99_vs_target_tps.svg",
        multi_line_chart_svg(x_tps, series_p99, "P99 延迟 vs 目标 TPS", "target_tps", "P99(ms)"),
    )


if __name__ == "__main__":
    main()
