import argparse
import csv
import json
import os
import shlex
from pathlib import Path
from typing import Dict, List, Tuple

from analysis.svg_chart import multi_line_chart_svg, line_chart_svg
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner
from analysis.common_charts import append_tps_vs_tx_by_nodes_chart, parse_bool_flag


def parse_int_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate_metrics(points: List[Dict[str, float]]) -> Dict[str, float]:
    keys = set()
    for point in points:
        keys.update(point.keys())
    aggregated: Dict[str, float] = {}
    for key in keys:
        aggregated[key] = avg([float(point.get(key, 0.0)) for point in points])
    return aggregated


def write_svg(path: Path, content: str) -> None:
    if not content:
        return
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="实验二：tPBFT 共识性能与节点规模扩展性测试")
    parser.add_argument("--nodes", type=str, default="4,8,16,32")
    parser.add_argument("--tx", type=str, default="100,1000,10000")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--out", type=str, default="experiments/exp2_tpbft/report")
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
    artifact_root.mkdir(parents=True, exist_ok=True)

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    port_offset = int(os.environ.get("PORT_OFFSET", "0"))
    grpc_port = 9090 + port_offset
    rpc_port = 26657 + port_offset
    chain_id = os.environ.get("CHAIN_ID", "hcp-exp2")
    cli_binary_env = os.environ.get("CLI_BINARY", "").strip() or os.environ.get("HCPD_BINARY", "hcpd")
    if os.path.isabs(cli_binary_env):
        cli_binary = cli_binary_env
    elif "/" in cli_binary_env:
        cli_binary = str((project_root / cli_binary_env).resolve())
    else:
        cli_binary = cli_binary_env

    node_list = parse_int_list(args.nodes)
    tx_list = parse_int_list(args.tx)
    runner = ExperimentRunner(project_root=project_root)
    base_loadgen_args = shlex.split(args.loadgen_args)

    points: List[ExperimentPoint] = []

    for n in node_list:
        for tx in tx_list:
            samples: List[Dict[str, float]] = []
            for repeat_idx in range(1, args.repeat + 1):
                data_root = artifact_root / f"n_{n}" / f"tx_{tx}" / f"run_{repeat_idx}" / "data"
                log_root = artifact_root / f"n_{n}" / f"tx_{tx}" / f"run_{repeat_idx}" / "logs"
                data_root.mkdir(parents=True, exist_ok=True)
                log_root.mkdir(parents=True, exist_ok=True)

                os.environ["CONSENSUS_ENGINE"] = "tpbft"
                os.environ["TPBFT_NODE_COUNT"] = str(n)
                os.environ["TPBFT_MIN_TRUST"] = os.environ.get("TPBFT_MIN_TRUST", "0.6")
                os.environ["TPBFT_MAX_VALIDATORS"] = os.environ.get("TPBFT_MAX_VALIDATORS", "100")
                os.environ["TPBFT_HISTORY_WINDOW"] = os.environ.get("TPBFT_HISTORY_WINDOW", "100")
                os.environ["INCLUDE_LOOPBACK"] = "true"

                matrix = [{"nodes": n, "tx": tx}]
                loadgen_args: List[str] = []
                for arg in base_loadgen_args:
                    value = (
                        arg.replace("{data_root}", str(data_root))
                        .replace("{nodes}", str(n))
                        .replace("{tx}", str(tx))
                        .replace("{cli_binary}", cli_binary)
                        .replace("{grpc_port}", str(grpc_port))
                        .replace("{rpc_port}", str(rpc_port))
                        .replace("{chain_id}", chain_id)
                    )
                    loadgen_args.append(value)

                print(
                    f"正在运行实验点: 节点={n}, 交易数={tx}, 重复={repeat_idx}/{args.repeat}",
                    flush=True,
                )
                result = runner.run(
                    name="实验二：tPBFT 共识性能与节点规模扩展性测试",
                    description=f"tPBFT nodes={n} tx={tx} repeat={repeat_idx}",
                    matrix=matrix,
                    data_root=data_root,
                    log_root=log_root,
                    loadgen_args=loadgen_args,
                )
                if result.points:
                    samples.append(result.points[0].metrics)

            aggregated = aggregate_metrics(samples)
            points.append(
                ExperimentPoint(
                    params={"nodes": n, "tx": tx},
                    metrics=aggregated,
                )
            )

    exp_result = ExperimentResult(
        name="实验二：tPBFT 共识性能与节点规模扩展性测试",
        description="tPBFT 信任增强型 PBFT 共识在不同节点规模与交易量下的性能边界评估",
        points=points,
        metadata={
            "nodes": node_list,
            "tx": tx_list,
            "repeat": args.repeat,
        },
    )
    result_path = output_dir / "result.json"
    runner.save_result(result_path, exp_result)

    write_outputs(output_dir, figures_dir, points, args)
    print(f"实验二报告已生成至: {output_dir}", flush=True)


def write_outputs(output_dir: Path, figures_dir: Path, points: List[ExperimentPoint], args) -> None:
    rows: List[Dict[str, float]] = []
    for p in points:
        nodes = float(p.params.get("nodes", 0))
        tx = float(p.params.get("tx", 0))
        m = p.metrics
        rows.append(
            {
                "nodes": nodes,
                "tx": tx,
                "tps": float(m.get("tps", 0.0)),
                "avg_confirm_time_ms": float(m.get("avg_confirm_time_ms", 0.0)),
                "p50_ms": float(m.get("p50_ms", 0.0)),
                "p95_ms": float(m.get("p95_ms", 0.0)),
                "p99_ms": float(m.get("p99_ms", 0.0)),
                "avg_block_time_ms": float(m.get("avg_block_time_ms", 0.0)),
                "cpu_percent": float(m.get("cpu_percent", 0.0)),
                "mem_bytes": float(m.get("mem_bytes", 0.0)),
                "net_mbps": float(m.get("net_mbps", 0.0)),
                "io_util": float(m.get("io_util", 0.0)),
                "rocksdb_write_amplification": float(m.get("rocksdb_write_amplification", 0.0)),
                "rocksdb_compaction_ms": float(m.get("rocksdb_compaction_ms", 0.0)),
            }
        )

    csv_path = output_dir / "exp2_summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    if not points:
        return

    nodes_sorted = sorted({int(p.params.get("nodes", 0)) for p in points if int(p.params.get("nodes", 0)) > 0})
    tx_sorted = sorted({int(p.params.get("tx", 0)) for p in points if int(p.params.get("tx", 0)) > 0})

    tps_by_nodes: Dict[Tuple[int, int], float] = {}
    p99_by_nodes: Dict[Tuple[int, int], float] = {}
    block_time_by_nodes: Dict[Tuple[int, int], float] = {}
    for p in points:
        n = int(p.params.get("nodes", 0))
        t = int(p.params.get("tx", 0))
        tps_by_nodes[(n, t)] = float(p.metrics.get("tps", 0.0))
        p99_by_nodes[(n, t)] = float(p.metrics.get("p99_ms", 0.0))
        block_time_by_nodes[(n, t)] = float(p.metrics.get("avg_block_time_ms", 0.0))

    x_nodes = [float(n) for n in nodes_sorted]
    series_tps: List[Tuple[str, List[float]]] = []
    for t in tx_sorted:
        ys = [tps_by_nodes.get((n, t), 0.0) for n in nodes_sorted]
        series_tps.append((f"tx={t}", ys))
    write_svg(
        figures_dir / "tps_vs_nodes.svg",
        multi_line_chart_svg(x_nodes, series_tps, "tPBFT TPS vs 节点数", "节点数", "TPS"),
    )

    series_p99: List[Tuple[str, List[float]]] = []
    for t in tx_sorted:
        ys = [p99_by_nodes.get((n, t), 0.0) for n in nodes_sorted]
        series_p99.append((f"tx={t}", ys))
    write_svg(
        figures_dir / "p99_vs_nodes.svg",
        multi_line_chart_svg(x_nodes, series_p99, "tPBFT P99 延迟 vs 节点数", "节点数", "P99(ms)"),
    )

    series_block: List[Tuple[str, List[float]]] = []
    for t in tx_sorted:
        ys = [block_time_by_nodes.get((n, t), 0.0) for n in nodes_sorted]
        series_block.append((f"tx={t}", ys))
    write_svg(
        figures_dir / "block_time_vs_nodes.svg",
        multi_line_chart_svg(x_nodes, series_block, "tPBFT 平均出块时间 vs 节点数", "节点数", "Block Time(ms)"),
    )

    chart_points = [
        {
            "params": {"nodes": n, "tx": t},
            "metrics": {"tps": tps_by_nodes.get((n, t), 0.0)},
        }
        for n in nodes_sorted
        for t in tx_sorted
    ]
    figures = [
        str(figures_dir / "tps_vs_nodes.svg"),
        str(figures_dir / "p99_vs_nodes.svg"),
        str(figures_dir / "block_time_vs_nodes.svg"),
    ]
    append_tps_vs_tx_by_nodes_chart(
        figures=figures,
        points=chart_points,
        output_dir=output_dir,
        figures_dir=figures_dir,
        line_figure_name="exp2_tps_vs_tx_by_nodes.svg",
        bar_figure_name="exp2_tps_vs_tx_by_nodes_bar.svg",
        title="实验2 tPBFT 性能曲线（TPS）",
        line_chart=parse_bool_flag(args.line_chart, True),
        bar_chart=parse_bool_flag(args.bar_chart, True),
    )


if __name__ == "__main__":
    main()
