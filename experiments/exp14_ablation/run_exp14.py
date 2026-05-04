#!/usr/bin/env python3
"""
实验十四：消融实验（Ablation Study）
基于 exp5 框架，验证 HCP 系统各优化模块的独立贡献与正交叠加效果。

实验组：
  A - 基线 tPBFT（无优化）
  B - 并行 Merkle 哈希（计算层优化）
  C - 分层架构（通信架构优化）
  D - 轻量分层（子层 Raft 简化）
  E - 热点感知（负载感知优化）
  F - 组合优化（全部叠加）
"""

import argparse
import csv
import json
import os
import shlex
import statistics
from pathlib import Path
from typing import Dict, List, Any

from analysis.common_charts import append_tps_vs_tx_by_nodes_chart, parse_bool_flag
from analysis.svg_chart import line_chart_svg
from collector.log_parser import (
    parse_hierarchical_tpbft_metrics,
    parse_hierarchical_hotspot_tpbft_metrics,
    parse_hierarchical_lightweight_tpbft_metrics,
    parse_hierarchical_tpbft_parallel_block_metrics,
)
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner


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


def bar_chart_svg(
    labels: List[str],
    values: List[float],
    title: str,
    x_label: str,
    y_label: str,
    colors: List[str] = None,
    errors: List[float] = None,
    y_min: float = None,
    width: int = 800,
    height: int = 480,
) -> str:
    if not labels or not values or len(labels) != len(values):
        return ""
    padding_left = 70
    padding_right = 30
    padding_top = 50
    padding_bottom = 80
    chart_width = width - padding_left - padding_right
    chart_height = height - padding_top - padding_bottom
    n = len(values)
    if y_min is None:
        y_min = 0.0
    y_max = max(values) if values else 1.0
    if errors:
        y_max = max(y_max, max(v + e for v, e in zip(values, errors)))
    if y_max <= y_min:
        y_max = y_min + 1

    def scale_y(value: float) -> float:
        return padding_top + (y_max - value) / (y_max - y_min) * chart_height

    bar_width = chart_width / n * 0.6
    gap = chart_width / n * 0.4
    rects = []
    error_lines = []
    text_labels = []
    for i, (label, value) in enumerate(zip(labels, values)):
        x = padding_left + gap / 2 + i * (bar_width + gap)
        y = scale_y(value)
        h = padding_top + chart_height - y
        color = colors[i] if colors and i < len(colors) else "#1976d2"
        rects.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{h:.2f}" fill="{color}" />')
        if errors and i < len(errors):
            err = errors[i]
            y_top = scale_y(value + err)
            y_bot = scale_y(value - err) if value - err >= y_min else scale_y(y_min)
            cx = x + bar_width / 2
            error_lines.append(
                f'<line x1="{cx:.2f}" y1="{y_top:.2f}" x2="{cx:.2f}" y2="{y_bot:.2f}" stroke="#333" stroke-width="1" />'
                f'<line x1="{cx - 5:.2f}" y1="{y_top:.2f}" x2="{cx + 5:.2f}" y2="{y_top:.2f}" stroke="#333" stroke-width="1" />'
                f'<line x1="{cx - 5:.2f}" y1="{y_bot:.2f}" x2="{cx + 5:.2f}" y2="{y_bot:.2f}" stroke="#333" stroke-width="1" />'
            )
        text_labels.append(
            f'<text x="{x + bar_width / 2:.2f}" y="{padding_top + chart_height + 20}" font-size="12" text-anchor="middle">{label}</text>'
        )

    ticks = 5
    y_ticks = []
    for i in range(ticks + 1):
        yv = y_min + (y_max - y_min) * i / ticks
        y_ticks.append((yv, scale_y(yv)))

    y_labels = []
    for value, y_pos in y_ticks:
        y_labels.append(f'<text x="{padding_left - 10}" y="{y_pos + 4:.2f}" font-size="12" text-anchor="end">{value:.2f}</text>')

    return f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="white" stroke="none"/>
  <text x="{width / 2}" y="24" font-size="16" text-anchor="middle">{title}</text>
  <line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{padding_top + chart_height}" stroke="#333" />
  <line x1="{padding_left}" y1="{padding_top + chart_height}" x2="{padding_left + chart_width}" y2="{padding_top + chart_height}" stroke="#333" />
  {"".join(rects)}
  {"".join(error_lines)}
  {"".join(text_labels)}
  {"".join(y_labels)}
  <text x="{width / 2}" y="{height - 12}" font-size="12" text-anchor="middle">{x_label}</text>
  <text x="16" y="{height / 2}" font-size="12" text-anchor="middle" transform="rotate(-90 16 {height / 2})">{y_label}</text>
</svg>
""".strip()


EXPERIMENTS = {
    "A": {
        "experiment_id": "exp_ablation_A",
        "consensus_engine": "tpbft",
        "parallel_merkle": False,
        "hierarchical": False,
        "sub_consensus": "pbft",
        "grouping_strategy": "random",
        "zipf_alpha": 0.0,
        "group_count": 1,
        "description": "基线 tPBFT：原始三阶段共识，无优化",
        "log_parser": "base",
    },
    "B": {
        "experiment_id": "exp_ablation_B",
        "consensus_engine": "tpbft-parallel-block",
        "parallel_merkle": True,
        "merkle_k": 8,
        "hierarchical": False,
        "sub_consensus": "pbft",
        "grouping_strategy": "random",
        "zipf_alpha": 0.0,
        "group_count": 1,
        "description": "块哈希优化：启用并行 Merkle 根计算",
        "log_parser": "parallel_block",
    },
    "C": {
        "experiment_id": "exp_ablation_C",
        "consensus_engine": "hierarchical-tpbft",
        "parallel_merkle": False,
        "hierarchical": True,
        "sub_consensus": "pbft",
        "grouping_strategy": "random",
        "zipf_alpha": 0.0,
        "group_count": 4,
        "description": "分层架构：主 PBFT + 子 PBFT，随机分组",
        "log_parser": "hierarchical",
    },
    "D": {
        "experiment_id": "exp_ablation_D",
        "consensus_engine": "hierarchical-lightweight-tpbft",
        "parallel_merkle": False,
        "hierarchical": True,
        "sub_consensus": "raft",
        "raft_heartbeat_ms": 50,
        "raft_election_ms": 200,
        "grouping_strategy": "random",
        "zipf_alpha": 0.0,
        "group_count": 4,
        "description": "轻量分层：主 PBFT + 子 Raft，随机分组",
        "log_parser": "lightweight",
    },
    "E": {
        "experiment_id": "exp_ablation_E",
        "consensus_engine": "hierarchical-hotspot-tpbft",
        "parallel_merkle": False,
        "hierarchical": True,
        "sub_consensus": "pbft",
        "grouping_strategy": "hash",
        "zipf_alpha": 1.8,
        "group_count": 4,
        "description": "热点感知：主 PBFT + 子 PBFT，哈希分组 + Zipf 负载",
        "log_parser": "hotspot",
    },
    "F": {
        "experiment_id": "exp_ablation_F",
        "consensus_engine": "hierarchical-tpbft-parallel-block",
        "parallel_merkle": True,
        "merkle_k": 8,
        "hierarchical": True,
        "sub_consensus": "raft",
        "raft_heartbeat_ms": 50,
        "raft_election_ms": 200,
        "grouping_strategy": "hash",
        "zipf_alpha": 1.8,
        "group_count": 4,
        "description": "组合优化：并行哈希 + 分层 + 子 Raft + 热点感知",
        "log_parser": "parallel_block",
    },
}


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
        "--account-count {account_count} "
        "--initial-nonce 0 "
        "--metrics-interval 100 "
        "--json-interval-ms 100 "
        "--csv-path {data_root}/loadgen.csv "
        "--chain-id {chain_id}"
    )


def setup_environment(config: Dict[str, Any], nodes: int) -> None:
    os.environ["CONSENSUS_ENGINE"] = config["consensus_engine"]
    os.environ["INCLUDE_LOOPBACK"] = "true"

    # 清理所有分层/子共识/热点相关环境变量
    for key in list(os.environ.keys()):
        if key.startswith("HIERARCHICAL_") or key in (
            "SUB_CONSENSUS", "RAFT_HEARTBEAT_MS", "RAFT_ELECTION_MS",
            "GROUPING_STRATEGY", "ZIPF_ALPHA", "MERKLE_K",
            "CROSS_GROUP_PENALTY_FACTOR",
        ):
            del os.environ[key]

    # 仅在分层模式下设置参数
    if config.get("hierarchical", False):
        g = config["group_count"]
        s = nodes // g
        os.environ["HIERARCHICAL_GROUP_COUNT"] = str(g)
        os.environ["HIERARCHICAL_GROUP_SIZE"] = str(s)
        os.environ["HIERARCHICAL_NODE_COUNT"] = str(nodes)
        os.environ["HIERARCHICAL_MESSAGE_BYTES"] = "256"
        os.environ["HIERARCHICAL_BASE_LATENCY_MS"] = "1.0"
        os.environ["HIERARCHICAL_PHASE_WEIGHT_INNER"] = "1.0"
        os.environ["HIERARCHICAL_PHASE_WEIGHT_OUTER"] = "1.0"
        os.environ["HIERARCHICAL_SIG_ALGO"] = "ed25519"
        os.environ["HIERARCHICAL_OUTER_MODE"] = "ed25519"
        os.environ["HIERARCHICAL_OUTER_SIG_ALGO"] = "ed25519"
        os.environ["HIERARCHICAL_BATCH_VERIFY"] = "true"
        os.environ["HIERARCHICAL_BATCH_VERIFY_GAIN"] = "3.0"
        os.environ["HIERARCHICAL_SIG_GEN_PARALLELISM"] = "2.0"
        os.environ["HIERARCHICAL_SIG_VERIFY_PARALLELISM"] = "2.0"
        os.environ["HIERARCHICAL_SIG_AGG_PARALLELISM"] = "1.0"
        os.environ["HIERARCHICAL_BATCH_SIZE"] = "200"

        # 子共识参数（仅分层模式有效）
        if config.get("sub_consensus"):
            os.environ["SUB_CONSENSUS"] = config["sub_consensus"]
        if config.get("raft_heartbeat_ms"):
            os.environ["RAFT_HEARTBEAT_MS"] = str(config["raft_heartbeat_ms"])
        if config.get("raft_election_ms"):
            os.environ["RAFT_ELECTION_MS"] = str(config["raft_election_ms"])

        # 热点感知参数（仅分层模式有效）
        if config.get("grouping_strategy"):
            os.environ["GROUPING_STRATEGY"] = config["grouping_strategy"]
        if config.get("zipf_alpha", 0.0) > 0.0:
            os.environ["ZIPF_ALPHA"] = str(config["zipf_alpha"])

    # 并行 Merkle 参数（不分层也可用）
    if config.get("parallel_merkle", False):
        os.environ["MERKLE_K"] = str(config.get("merkle_k", 8))


def parse_group_metrics(log_dir: Path, parser_type: str) -> Dict[str, List[float]]:
    if parser_type == "hierarchical":
        return parse_hierarchical_tpbft_metrics(log_dir)
    elif parser_type == "hotspot":
        return parse_hierarchical_hotspot_tpbft_metrics(log_dir)
    elif parser_type == "lightweight":
        return parse_hierarchical_lightweight_tpbft_metrics(log_dir)
    elif parser_type == "parallel_block":
        return parse_hierarchical_tpbft_parallel_block_metrics(log_dir)
    else:
        return {
            "pre_prepare_ms": [], "prepare_ms": [], "commit_ms": [],
            "comm_bytes": [], "total_messages": [],
            "sig_gen_count": [], "sig_verify_count": [],
            "sig_gen_time_ms": [], "sig_verify_time_ms": [],
            "aggregation_time_ms": [], "verify_time_ms": [],
            "sig_per_node": [], "sig_ops_per_tx": [],
            "batch_size": [], "batch_verify": [], "verify_gain": [],
            "sig_gen_parallelism": [], "sig_verify_parallelism": [], "sig_agg_parallelism": [],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="实验十四：消融实验")
    parser.add_argument("--groups", type=str, default="A,B,C,D,E,F")
    parser.add_argument("--nodes-list", type=str, default="16,32")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--target-tps", type=int, default=5000)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--account-count", type=int, default=100)
    parser.add_argument("--out", type=str, default="tests/exp14_ablation/report")
    parser.add_argument("--loadgen-args", type=str, default=build_default_loadgen_args())
    parser.add_argument("--line-chart", type=str, default="true")
    parser.add_argument("--bar-chart", type=str, default="true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[3]
    lab_root = project_root / "hcp-lab"
    out_path = Path(args.out)
    if not out_path.is_absolute():
        output_dir = project_root / out_path
    else:
        output_dir = out_path
    output_dir.mkdir(parents=True, exist_ok=True)

    artifact_override = os.environ.get("EXP_ARTIFACT_ROOT")
    if artifact_override:
        artifact_path = Path(artifact_override)
        artifact_root = artifact_path if artifact_path.is_absolute() else project_root / artifact_path
    else:
        artifact_root = project_root / "tests" / "exp14_ablation"
    artifact_root.mkdir(parents=True, exist_ok=True)
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    port_offset = int(os.environ.get("PORT_OFFSET", "0"))
    grpc_port = 9090 + port_offset
    rpc_port = 26657 + port_offset
    chain_id = os.environ.get("CHAIN_ID", "hcp-exp14")
    cli_binary_env = os.environ.get("HCPD_BINARY", "hcpd")
    if os.path.isabs(cli_binary_env):
        cli_binary = cli_binary_env
    elif "/" in cli_binary_env or cli_binary_env.startswith("."):
        cli_binary = str((lab_root / cli_binary_env).resolve())
    else:
        # fallback to project_root binary
        fallback = project_root / "hcp-consensus-build" / "hcpd"
        if fallback.exists():
            cli_binary = str(fallback.resolve())
        else:
            cli_binary = cli_binary_env

    group_keys = [g.strip().upper() for g in args.groups.split(",") if g.strip()]
    node_scales = [int(n.strip()) for n in args.nodes_list.split(",") if n.strip()]
    runner = ExperimentRunner(project_root=project_root)
    base_loadgen_args = shlex.split(args.loadgen_args)

    print(
        f"实验十四（消融实验）参数: groups={','.join(group_keys)} "
        f"nodes={','.join(str(n) for n in node_scales)} "
        f"repeat={args.repeat} duration={args.duration}s target_tps={args.target_tps}",
        flush=True,
    )
    print(f"实验输出目录: {output_dir}", flush=True)
    print(f"实验数据目录: {artifact_root}", flush=True)

    aggregated: Dict[str, Dict[int, Dict[str, float]]] = {}
    aggregated_std: Dict[str, Dict[int, Dict[str, float]]] = {}
    points: List[ExperimentPoint] = []

    for group_key in group_keys:
        config = EXPERIMENTS[group_key]
        aggregated[group_key] = {}
        aggregated_std[group_key] = {}

        for nodes in node_scales:
            samples: List[Dict[str, float]] = []
            for repeat_idx in range(1, args.repeat + 1):
                data_root = artifact_root / f"group_{group_key}" / f"nodes_{nodes}" / f"run_{repeat_idx}" / "data"
                log_root = artifact_root / f"group_{group_key}" / f"nodes_{nodes}" / f"run_{repeat_idx}" / "logs"
                data_root.mkdir(parents=True, exist_ok=True)
                log_root.mkdir(parents=True, exist_ok=True)

                setup_environment(config, nodes)

                loadgen_selection = ""
                if config.get("zipf_alpha", 0.0) > 0.0:
                    loadgen_selection = f"--account-selection-mode zipf --zipf-alpha {config['zipf_alpha']}"

                matrix = [{"nodes": nodes, "tx": args.target_tps * args.duration}]
                loadgen_args: List[str] = []
                for arg in base_loadgen_args:
                    value = (
                        arg.replace("{data_root}", str(data_root))
                        .replace("{nodes}", str(nodes))
                        .replace("{duration}", str(args.duration))
                        .replace("{target_tps}", str(args.target_tps))
                        .replace("{batch_size}", str(args.batch_size))
                        .replace("{account_count}", str(args.account_count))
                        .replace("{cli_binary}", cli_binary)
                        .replace("{grpc_port}", str(grpc_port))
                        .replace("{rpc_port}", str(rpc_port))
                        .replace("{chain_id}", chain_id)
                    )
                    loadgen_args.append(value)
                if loadgen_selection:
                    loadgen_args.extend(shlex.split(loadgen_selection))

                run_id = f"{config['experiment_id']}_n{nodes}_r{repeat_idx}"
                print(
                    f"[{group_key}] 启动实验点: nodes={nodes} run={repeat_idx} "
                    f"engine={config['consensus_engine']} run_id={run_id}",
                    flush=True,
                )
                if loadgen_args:
                    print("负载参数(展开预览): " + " ".join(loadgen_args), flush=True)

                result = runner.run(
                    name=f"实验十四：消融实验 - 组 {group_key}",
                    description=config["description"],
                    matrix=matrix,
                    data_root=data_root,
                    log_root=log_root,
                    loadgen_args=loadgen_args,
                    extra_account_count=args.account_count,
                )
                metrics = result.points[0].metrics if result.points else {}
                if "tps" not in metrics:
                    duration_s = float(metrics.get("duration_s", 0.0))
                    if duration_s > 0:
                        metrics["tps"] = float(args.target_tps * args.duration) / duration_s

                log_dir = log_root / f"nodes_{nodes}"
                group_metrics = parse_group_metrics(log_dir, config["log_parser"])
                duration_s = float(metrics.get("duration_s", 0.0))
                net_mbps = float(metrics.get("net_mbps", 0.0))
                net_bytes_total = net_mbps * 1024.0 * 1024.0 / 8.0 * duration_s if duration_s > 0 else 0.0

                sample = dict(metrics)
                sample["pre_prepare_ms"] = avg(group_metrics.get("pre_prepare_ms", []))
                sample["prepare_ms"] = avg(group_metrics.get("prepare_ms", []))
                sample["commit_ms"] = avg(group_metrics.get("commit_ms", []))
                sample["comm_bytes_per_block"] = avg(group_metrics.get("comm_bytes", []))
                sample["total_messages"] = avg(group_metrics.get("total_messages", []))
                sample["sig_gen_count"] = avg(group_metrics.get("sig_gen_count", []))
                sample["sig_verify_count"] = avg(group_metrics.get("sig_verify_count", []))
                sample["sig_gen_time_ms"] = avg(group_metrics.get("sig_gen_time_ms", []))
                sample["sig_verify_time_ms"] = avg(group_metrics.get("sig_verify_time_ms", []))
                sample["aggregation_time_ms"] = avg(group_metrics.get("aggregation_time_ms", []))
                sample["verify_time_ms"] = avg(group_metrics.get("verify_time_ms", []))
                sample["sig_per_node"] = avg(group_metrics.get("sig_per_node", []))
                sample["sig_ops_per_tx"] = avg(group_metrics.get("sig_ops_per_tx", []))
                sample["batch_size"] = avg(group_metrics.get("batch_size", []))
                sample["batch_verify"] = avg(group_metrics.get("batch_verify", []))
                sample["verify_gain"] = avg(group_metrics.get("verify_gain", []))
                sample["sig_gen_parallelism"] = avg(group_metrics.get("sig_gen_parallelism", []))
                sample["sig_verify_parallelism"] = avg(group_metrics.get("sig_verify_parallelism", []))
                sample["sig_agg_parallelism"] = avg(group_metrics.get("sig_agg_parallelism", []))
                sample["sig_total_time_ms"] = sample["sig_gen_time_ms"] + sample["sig_verify_time_ms"] + sample["aggregation_time_ms"]
                sample["net_bytes_total"] = net_bytes_total
                sample["cross_group_ratio"] = avg(group_metrics.get("cross_group_ratio", []))
                sample["sub_consensus_msg_count"] = avg(group_metrics.get("sub_messages", []))
                sample["merkle_subblock_time_ms"] = avg(group_metrics.get("subblock_time_ms", []))
                sample["merkle_merge_time_ms"] = avg(group_metrics.get("merge_time_ms", []))

                samples.append(sample)
                print(
                    f"[{group_key}] 完成: {run_id} TPS={sample.get('tps', 0.0):.2f} "
                    f"P99={sample.get('p99_ms', 0.0):.2f}ms "
                    f"CrossGroup={sample.get('cross_group_ratio', 0.0):.4f}",
                    flush=True,
                )

            if not samples:
                continue

            agg: Dict[str, float] = {}
            agg_std: Dict[str, float] = {}
            keys = samples[0].keys()
            for key in keys:
                values = [float(s.get(key, 0.0)) for s in samples]
                agg[key] = avg(values)
                agg_std[key] = stddev(values)
            aggregated[group_key][nodes] = agg
            aggregated_std[group_key][nodes] = agg_std
            points.append(
                ExperimentPoint(
                    params={
                        "group": group_key,
                        "nodes": nodes,
                        "group_count": config["group_count"],
                        "consensus_engine": config["consensus_engine"],
                        "zipf_alpha": config["zipf_alpha"],
                    },
                    metrics=agg,
                )
            )

    result = ExperimentResult(
        name="实验十四：消融实验",
        description="验证 HCP 各优化模块的独立贡献与正交叠加效果",
        points=points,
        metadata={
            "groups": group_keys,
            "node_scales": node_scales,
            "repeat": args.repeat,
            "duration_sec": args.duration,
            "target_tps": args.target_tps,
        },
    )
    result_path = output_dir / "result.json"
    runner.save_result(result_path, result)

    rows: List[Dict[str, Any]] = []
    for group_key in group_keys:
        for nodes in sorted(aggregated.get(group_key, {}).keys()):
            metrics = aggregated[group_key][nodes]
            stds = aggregated_std[group_key][nodes]
            rows.append({
                "group": group_key,
                "nodes": nodes,
                "tps_avg": metrics.get("tps", 0.0),
                "tps_std": stds.get("tps", 0.0),
                "avg_latency_avg": metrics.get("avg_confirm_time_ms", 0.0),
                "avg_latency_std": stds.get("avg_confirm_time_ms", 0.0),
                "p50_avg": metrics.get("p50_ms", 0.0),
                "p50_std": stds.get("p50_ms", 0.0),
                "p99_avg": metrics.get("p99_ms", 0.0),
                "p99_std": stds.get("p99_ms", 0.0),
                "sig_total_time_avg": metrics.get("sig_total_time_ms", 0.0),
                "sig_total_time_std": stds.get("sig_total_time_ms", 0.0),
                "total_messages_avg": metrics.get("total_messages", 0.0),
                "total_messages_std": stds.get("total_messages", 0.0),
                "comm_bytes_avg": metrics.get("comm_bytes_per_block", 0.0),
                "comm_bytes_std": stds.get("comm_bytes_per_block", 0.0),
                "net_bytes_total_avg": metrics.get("net_bytes_total", 0.0),
                "net_bytes_total_std": stds.get("net_bytes_total", 0.0),
                "cpu_avg": metrics.get("cpu_percent", 0.0),
                "cpu_std": stds.get("cpu_percent", 0.0),
                "cross_group_ratio_avg": metrics.get("cross_group_ratio", 0.0),
                "cross_group_ratio_std": stds.get("cross_group_ratio", 0.0),
                "sub_consensus_msg_count_avg": metrics.get("sub_consensus_msg_count", 0.0),
                "sub_consensus_msg_count_std": stds.get("sub_consensus_msg_count", 0.0),
            })

    csv_path = output_dir / "exp14_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    _plot_ablation_charts(
        aggregated=aggregated,
        aggregated_std=aggregated_std,
        group_keys=group_keys,
        node_scales=node_scales,
        figures_dir=figures_dir,
        output_dir=output_dir,
        points=points,
        args=args,
    )

    print("实验十四全部完成", flush=True)


def _plot_ablation_charts(
    aggregated: Dict[str, Dict[int, Dict[str, float]]],
    aggregated_std: Dict[str, Dict[int, Dict[str, float]]],
    group_keys: List[str],
    node_scales: List[int],
    figures_dir: Path,
    output_dir: Path,
    points: List[ExperimentPoint],
    args: argparse.Namespace,
) -> None:
    group_labels = {
        "A": "Baseline",
        "B": "Parallel\\nHash",
        "C": "Hierarchical",
        "D": "Lightweight",
        "E": "Hotspot\\nAware",
        "F": "Combined",
    }
    group_colors = {
        "A": "#d62728",
        "B": "#ff7f0e",
        "C": "#2ca02c",
        "D": "#1f77b4",
        "E": "#9467bd",
        "F": "#8c564b",
    }

    for nodes in node_scales:
        tps_values = []
        tps_errs = []
        labels = []
        colors = []
        for g in group_keys:
            if nodes in aggregated.get(g, {}):
                tps_values.append(aggregated[g][nodes].get("tps", 0.0))
                tps_errs.append(aggregated_std[g][nodes].get("tps", 0.0))
                labels.append(group_labels.get(g, g))
                colors.append(group_colors.get(g, "#333333"))
        if tps_values:
            svg = bar_chart_svg(
                labels=labels,
                values=tps_values,
                title=f"消融实验 TPS 对比 ({nodes} 节点)",
                x_label="实验组",
                y_label="Throughput (TPS)",
                colors=colors,
                errors=tps_errs,
                y_min=0,
            )
            write_svg(figures_dir / f"ablation_tps_{nodes}nodes.svg", svg)

    for nodes in node_scales:
        p99_values = []
        p99_errs = []
        labels = []
        colors = []
        for g in group_keys:
            if nodes in aggregated.get(g, {}):
                p99_values.append(aggregated[g][nodes].get("p99_ms", 0.0))
                p99_errs.append(aggregated_std[g][nodes].get("p99_ms", 0.0))
                labels.append(group_labels.get(g, g))
                colors.append(group_colors.get(g, "#333333"))
        if p99_values:
            svg = bar_chart_svg(
                labels=labels,
                values=p99_values,
                title=f"消融实验 P99 延迟对比 ({nodes} 节点)",
                x_label="实验组",
                y_label="P99 Latency (ms)",
                colors=colors,
                errors=p99_errs,
                y_min=0,
            )
            write_svg(figures_dir / f"ablation_p99_{nodes}nodes.svg", svg)

    cross_group_data: Dict[str, Dict[int, float]] = {}
    for g in group_keys:
        if g in ("C", "D", "E", "F"):
            cross_group_data[g] = {}
            for nodes in node_scales:
                if nodes in aggregated.get(g, {}):
                    cross_group_data[g][nodes] = aggregated[g][nodes].get("cross_group_ratio", 0.0)
    if cross_group_data:
        for nodes in node_scales:
            cg_values = []
            cg_labels = []
            cg_colors = []
            for g in group_keys:
                if g in cross_group_data and nodes in cross_group_data[g]:
                    cg_values.append(cross_group_data[g][nodes])
                    cg_labels.append(group_labels.get(g, g))
                    cg_colors.append(group_colors.get(g, "#333333"))
            if cg_values:
                svg = bar_chart_svg(
                    labels=cg_labels,
                    values=cg_values,
                    title=f"跨组事务率 ({nodes} 节点)",
                    x_label="实验组",
                    y_label="Cross-Group Ratio",
                    colors=cg_colors,
                    y_min=0,
                )
                write_svg(figures_dir / f"ablation_crossgroup_{nodes}nodes.svg", svg)

    for g in group_keys:
        tps_vals = []
        for nodes in node_scales:
            if nodes in aggregated.get(g, {}):
                tps_vals.append(aggregated[g][nodes].get("tps", 0.0))
        if tps_vals:
            svg = line_chart_svg(
                x_values=[float(n) for n in node_scales],
                y_values=tps_vals,
                title=f"组 {g} TPS 随节点规模变化",
                x_label="Nodes",
                y_label="TPS",
            )
            write_svg(figures_dir / f"ablation_scale_group{g}.svg", svg)

    extra_figures: List[str] = []
    append_tps_vs_tx_by_nodes_chart(
        figures=extra_figures,
        points=points,
        output_dir=output_dir,
        figures_dir=figures_dir,
        line_figure_name="exp14_tps_vs_nodes.svg",
        bar_figure_name="exp14_tps_vs_nodes_bar.svg",
        title="实验14 消融实验 TPS 性能",
        line_chart=parse_bool_flag(args.line_chart, True),
        bar_chart=parse_bool_flag(args.bar_chart, True),
    )

    summary = {
        "groups": group_keys,
        "node_scales": node_scales,
        "repeat": args.repeat,
        "duration_sec": args.duration,
        "target_tps": args.target_tps,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
