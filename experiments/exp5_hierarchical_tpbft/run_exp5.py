import argparse
import csv
import json
import os
import shlex
import statistics
from pathlib import Path
from typing import Dict, List

from analysis.svg_chart import line_chart_svg
from collector.log_parser import parse_hierarchical_tpbft_metrics
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner


def parse_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def parse_algo_list(value: str) -> List[str]:
    return [v.strip().lower() for v in value.split(",") if v.strip()]


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


def main() -> None:
    parser = argparse.ArgumentParser(description="实验五：分层 TPBFT")
    parser.add_argument("--groups", type=str, default="32,16,8,4,2")
    parser.add_argument("--nodes", type=int, default=32)
    parser.add_argument("--tx", type=int, default=100)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--sig-algos", type=str, default="bls,ed25519")
    parser.add_argument("--out", type=str, default="experiments/exp5_hierarchical_tpbft/report")
    parser.add_argument("--message-bytes", type=int, default=256)
    parser.add_argument("--base-latency-ms", type=float, default=1.0)
    parser.add_argument("--phase-weight-inner", type=float, default=1.0)
    parser.add_argument("--phase-weight-outer", type=float, default=1.0)
    parser.add_argument("--sig-gen-ms", type=float, default=0.0)
    parser.add_argument("--sig-verify-ms", type=float, default=0.0)
    parser.add_argument("--sig-agg-ms", type=float, default=0.0)
    parser.add_argument("--outer-mode", type=str, default="ed25519")
    parser.add_argument("--outer-sig-algo", type=str, default="")
    parser.add_argument("--outer-sig-gen-ms", type=float, default=0.0)
    parser.add_argument("--outer-sig-verify-ms", type=float, default=0.0)
    parser.add_argument("--outer-sig-agg-ms", type=float, default=0.0)
    parser.add_argument("--batch-verify", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--batch-verify-gain", type=float, default=3.0)
    parser.add_argument("--sig-gen-parallelism", type=float, default=2.0)
    parser.add_argument("--sig-verify-parallelism", type=float, default=2.0)
    parser.add_argument("--sig-agg-parallelism", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--loadgen-args", type=str, default=build_default_loadgen_args())
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

    port_offset = int(os.environ.get("PORT_OFFSET", "0"))
    grpc_port = 9090 + port_offset
    rpc_port = 26657 + port_offset
    chain_id = os.environ.get("CHAIN_ID", "hcp-exp5")
    cli_binary_env = os.environ.get("HCPD_BINARY", "hcpd")
    if os.path.isabs(cli_binary_env):
        cli_binary = cli_binary_env
    elif "/" in cli_binary_env or cli_binary_env.startswith("."):
        cli_binary = str((lab_root / cli_binary_env).resolve())
    else:
        cli_binary = cli_binary_env

    groups = parse_list(args.groups)
    sig_algos = parse_algo_list(args.sig_algos)
    runner = ExperimentRunner(project_root=project_root)
    base_loadgen_args = shlex.split(args.loadgen_args)

    print(
        "实验五参数: nodes={nodes} tx={tx} groups={groups} repeat={repeat} sig_algos={sig_algos} outer_mode={outer_mode} batch_verify={batch_verify} batch_size={batch_size}".format(
            nodes=args.nodes,
            tx=args.tx,
            groups=",".join(str(g) for g in groups),
            repeat=args.repeat,
            sig_algos=",".join(sig_algos),
            outer_mode=args.outer_mode,
            batch_verify=args.batch_verify,
            batch_size=args.batch_size,
        ),
        flush=True,
    )
    print(f"实验输出目录: {output_dir}", flush=True)
    print(f"实验数据目录: {artifact_root}", flush=True)

    aggregated: Dict[str, Dict[int, Dict[str, float]]] = {}
    aggregated_std: Dict[str, Dict[int, Dict[str, float]]] = {}
    points: List[ExperimentPoint] = []

    for algo in sig_algos:
        aggregated[algo] = {}
        aggregated_std[algo] = {}
        for g in groups:
            if g <= 0 or args.nodes % g != 0:
                continue
            s = args.nodes // g
            samples: List[Dict[str, float]] = []
            for repeat_idx in range(1, args.repeat + 1):
                data_root = artifact_root / f"algo_{algo}" / f"g_{g}" / f"run_{repeat_idx}" / "data"
                log_root = artifact_root / f"algo_{algo}" / f"g_{g}" / f"run_{repeat_idx}" / "logs"
                data_root.mkdir(parents=True, exist_ok=True)
                log_root.mkdir(parents=True, exist_ok=True)

                os.environ["CONSENSUS_ENGINE"] = "hierarchical-tpbft"
                os.environ["HIERARCHICAL_GROUP_COUNT"] = str(g)
                os.environ["HIERARCHICAL_GROUP_SIZE"] = str(s)
                os.environ["HIERARCHICAL_NODE_COUNT"] = str(args.nodes)
                os.environ["HIERARCHICAL_MESSAGE_BYTES"] = str(args.message_bytes)
                os.environ["HIERARCHICAL_BASE_LATENCY_MS"] = str(args.base_latency_ms)
                os.environ["HIERARCHICAL_PHASE_WEIGHT_INNER"] = str(args.phase_weight_inner)
                os.environ["HIERARCHICAL_PHASE_WEIGHT_OUTER"] = str(args.phase_weight_outer)
                os.environ["HIERARCHICAL_SIG_ALGO"] = algo
                if args.sig_gen_ms > 0:
                    os.environ["HIERARCHICAL_SIG_GEN_MS"] = str(args.sig_gen_ms)
                if args.sig_verify_ms > 0:
                    os.environ["HIERARCHICAL_SIG_VERIFY_MS"] = str(args.sig_verify_ms)
                if args.sig_agg_ms > 0:
                    os.environ["HIERARCHICAL_SIG_AGG_MS"] = str(args.sig_agg_ms)
                os.environ["HIERARCHICAL_OUTER_MODE"] = args.outer_mode
                outer_algo = args.outer_sig_algo.strip()
                if not outer_algo:
                    outer_algo = "ed25519" if args.outer_mode.lower() == "ed25519" else algo
                os.environ["HIERARCHICAL_OUTER_SIG_ALGO"] = outer_algo
                if args.outer_sig_gen_ms > 0:
                    os.environ["HIERARCHICAL_OUTER_SIG_GEN_MS"] = str(args.outer_sig_gen_ms)
                if args.outer_sig_verify_ms > 0:
                    os.environ["HIERARCHICAL_OUTER_SIG_VERIFY_MS"] = str(args.outer_sig_verify_ms)
                if args.outer_sig_agg_ms > 0:
                    os.environ["HIERARCHICAL_OUTER_SIG_AGG_MS"] = str(args.outer_sig_agg_ms)
                os.environ["HIERARCHICAL_BATCH_VERIFY"] = "true" if args.batch_verify else "false"
                if args.batch_verify_gain > 0:
                    os.environ["HIERARCHICAL_BATCH_VERIFY_GAIN"] = str(args.batch_verify_gain)
                if args.sig_gen_parallelism > 0:
                    os.environ["HIERARCHICAL_SIG_GEN_PARALLELISM"] = str(args.sig_gen_parallelism)
                if args.sig_verify_parallelism > 0:
                    os.environ["HIERARCHICAL_SIG_VERIFY_PARALLELISM"] = str(args.sig_verify_parallelism)
                if args.sig_agg_parallelism > 0:
                    os.environ["HIERARCHICAL_SIG_AGG_PARALLELISM"] = str(args.sig_agg_parallelism)
                os.environ["HIERARCHICAL_BATCH_SIZE"] = str(args.batch_size)
                os.environ["INCLUDE_LOOPBACK"] = "true"

                matrix = [{"nodes": args.nodes, "tx": args.tx}]
                loadgen_args: List[str] = []
                for arg in base_loadgen_args:
                    value = (
                        arg.replace("{data_root}", str(data_root))
                        .replace("{nodes}", str(args.nodes))
                        .replace("{tx}", str(args.tx))
                        .replace("{g}", str(g))
                        .replace("{s}", str(s))
                        .replace("{algo}", algo)
                        .replace("{batch_size}", str(args.batch_size))
                        .replace("{cli_binary}", cli_binary)
                        .replace("{grpc_port}", str(grpc_port))
                        .replace("{rpc_port}", str(rpc_port))
                        .replace("{chain_id}", chain_id)
                    )
                    loadgen_args.append(value)
                print(
                    "实验点参数: algo={algo} g={g} s={s} run={run} data_root={data_root} log_root={log_root}".format(
                        algo=algo,
                        g=g,
                        s=s,
                        run=repeat_idx,
                        data_root=data_root,
                        log_root=log_root,
                    ),
                    flush=True,
                )
                if loadgen_args:
                    print("负载参数(展开预览): " + " ".join(loadgen_args), flush=True)

                result = runner.run(
                    name="实验五：分层 TPBFT",
                    description="分层 TPBFT 线性通信与瓶颈迁移验证",
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
                log_dir = log_root / f"nodes_{args.nodes}"
                tpbft_metrics = parse_hierarchical_tpbft_metrics(log_dir)
                duration_s = float(metrics.get("duration_s", 0.0))
                net_mbps = float(metrics.get("net_mbps", 0.0))
                net_bytes_total = net_mbps * 1024.0 * 1024.0 / 8.0 * duration_s if duration_s > 0 else 0.0

                sample = dict(metrics)
                sample["pre_prepare_ms"] = avg(tpbft_metrics.get("pre_prepare_ms", []))
                sample["prepare_ms"] = avg(tpbft_metrics.get("prepare_ms", []))
                sample["commit_ms"] = avg(tpbft_metrics.get("commit_ms", []))
                sample["comm_bytes_per_block"] = avg(tpbft_metrics.get("comm_bytes", []))
                sample["total_messages"] = avg(tpbft_metrics.get("total_messages", []))
                sample["sig_gen_count"] = avg(tpbft_metrics.get("sig_gen_count", []))
                sample["sig_verify_count"] = avg(tpbft_metrics.get("sig_verify_count", []))
                sample["sig_gen_time_ms"] = avg(tpbft_metrics.get("sig_gen_time_ms", []))
                sample["sig_verify_time_ms"] = avg(tpbft_metrics.get("sig_verify_time_ms", []))
                sample["aggregation_time_ms"] = avg(tpbft_metrics.get("aggregation_time_ms", []))
                sample["verify_time_ms"] = avg(tpbft_metrics.get("verify_time_ms", []))
                sample["sig_per_node"] = avg(tpbft_metrics.get("sig_per_node", []))
                sample["sig_ops_per_tx"] = avg(tpbft_metrics.get("sig_ops_per_tx", []))
                sample["batch_size"] = avg(tpbft_metrics.get("batch_size", []))
                sample["batch_verify"] = avg(tpbft_metrics.get("batch_verify", []))
                sample["verify_gain"] = avg(tpbft_metrics.get("verify_gain", []))
                sample["sig_gen_parallelism"] = avg(tpbft_metrics.get("sig_gen_parallelism", []))
                sample["sig_verify_parallelism"] = avg(tpbft_metrics.get("sig_verify_parallelism", []))
                sample["sig_agg_parallelism"] = avg(tpbft_metrics.get("sig_agg_parallelism", []))
                sample["sig_total_time_ms"] = (
                    sample["sig_gen_time_ms"]
                    + sample["sig_verify_time_ms"]
                    + sample["aggregation_time_ms"]
                )
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
            aggregated[algo][g] = agg
            aggregated_std[algo][g] = agg_std
            points.append(
                ExperimentPoint(
                    params={"algo": algo, "g": g, "s": s, "nodes": args.nodes},
                    metrics=agg,
                )
            )

    result = ExperimentResult(
        name="实验五：分层 TPBFT",
        description="验证分层 TPBFT 通信复杂度与签名瓶颈迁移",
        points=points,
        metadata={
            "groups": groups,
            "nodes": args.nodes,
            "tx": args.tx,
            "repeat": args.repeat,
            "sig_algos": sig_algos,
            "outer_mode": args.outer_mode,
            "batch_verify": args.batch_verify,
            "batch_size": args.batch_size,
        },
    )
    result_path = output_dir / "result.json"
    runner.save_result(result_path, result)

    rows: List[Dict[str, float | str]] = []
    for algo in sig_algos:
        for g in sorted(aggregated.get(algo, {}).keys()):
            s = args.nodes // g
            metrics = aggregated[algo][g]
            stds = aggregated_std[algo][g]
            rows.append(
                {
                    "algo": algo,
                    "g": g,
                    "s": s,
                    "tps_avg": metrics.get("tps", 0.0),
                    "tps_std": stds.get("tps", 0.0),
                    "avg_latency_avg": metrics.get("avg_confirm_time_ms", 0.0),
                    "avg_latency_std": stds.get("avg_confirm_time_ms", 0.0),
                    "p99_avg": metrics.get("p99_ms", 0.0),
                    "p99_std": stds.get("p99_ms", 0.0),
                    "sig_gen_time_avg": metrics.get("sig_gen_time_ms", 0.0),
                    "sig_verify_time_avg": metrics.get("sig_verify_time_ms", 0.0),
                    "aggregation_time_avg": metrics.get("aggregation_time_ms", 0.0),
                    "verify_time_avg": metrics.get("verify_time_ms", 0.0),
                    "sig_total_time_avg": metrics.get("sig_total_time_ms", 0.0),
                    "sig_gen_count_avg": metrics.get("sig_gen_count", 0.0),
                    "sig_verify_count_avg": metrics.get("sig_verify_count", 0.0),
                    "sig_per_node_avg": metrics.get("sig_per_node", 0.0),
                    "sig_ops_per_tx_avg": metrics.get("sig_ops_per_tx", 0.0),
                    "batch_size_avg": metrics.get("batch_size", 0.0),
                    "batch_verify_avg": metrics.get("batch_verify", 0.0),
                    "verify_gain_avg": metrics.get("verify_gain", 0.0),
                    "sig_gen_parallelism_avg": metrics.get("sig_gen_parallelism", 0.0),
                    "sig_verify_parallelism_avg": metrics.get("sig_verify_parallelism", 0.0),
                    "sig_agg_parallelism_avg": metrics.get("sig_agg_parallelism", 0.0),
                    "total_messages_avg": metrics.get("total_messages", 0.0),
                    "comm_bytes_avg": metrics.get("comm_bytes_per_block", 0.0),
                    "net_bytes_total_avg": metrics.get("net_bytes_total", 0.0),
                    "cpu_avg": metrics.get("cpu_percent", 0.0),
                }
            )

    csv_path = output_dir / "exp5_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    for algo in sig_algos:
        g_sorted = sorted(aggregated.get(algo, {}).keys())
        if not g_sorted:
            continue
        tps_values = [aggregated[algo][g].get("tps", 0.0) for g in g_sorted]
        msg_values = [aggregated[algo][g].get("total_messages", 0.0) for g in g_sorted]
        sig_values = [aggregated[algo][g].get("sig_total_time_ms", 0.0) for g in g_sorted]
        net_values = [aggregated[algo][g].get("net_bytes_total", 0.0) for g in g_sorted]
        cpu_values = [aggregated[algo][g].get("cpu_percent", 0.0) for g in g_sorted]

        write_svg(
            figures_dir / f"tps_vs_g_{algo}.svg",
            line_chart_svg([float(g) for g in g_sorted], tps_values, f"TPS vs g ({algo})", "g", "TPS"),
        )
        write_svg(
            figures_dir / f"messages_vs_g_{algo}.svg",
            line_chart_svg(
                [float(g) for g in g_sorted], msg_values, f"通信消息数 vs g ({algo})", "g", "messages"
            ),
        )
        write_svg(
            figures_dir / f"sig_time_vs_g_{algo}.svg",
            line_chart_svg(
                [float(g) for g in g_sorted], sig_values, f"阈值签名耗时 vs g ({algo})", "g", "time(ms)"
            ),
        )
        write_svg(
            figures_dir / f"net_bytes_vs_g_{algo}.svg",
            line_chart_svg(
                [float(g) for g in g_sorted], net_values, f"网络总字节 vs g ({algo})", "g", "bytes"
            ),
        )
        write_svg(
            figures_dir / f"cpu_vs_g_{algo}.svg",
            line_chart_svg(
                [float(g) for g in g_sorted], cpu_values, f"CPU 使用率 vs g ({algo})", "g", "cpu(%)"
            ),
        )

    summary = {
        "groups": groups,
        "sig_algos": sig_algos,
        "nodes": args.nodes,
        "tx": args.tx,
        "repeat": args.repeat,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
