import argparse
import os
import shlex
import time
from pathlib import Path
from typing import List

from analysis.common_charts import append_tps_vs_tx_by_nodes_chart, parse_bool_flag
from analysis.svg_chart import line_chart_svg
from collector.log_parser import parse_block_times, parse_confirm_times
from collector.system_monitor import SystemMonitor
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner
from controller.node_manager import NodeManager
from report.exporter import export_markdown, export_pdf


def parse_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def avg_nonzero(values: List[float]) -> float:
    filtered = [v for v in values if v > 0]
    return sum(filtered) / len(filtered) if filtered else 0.0


def write_svg(path: Path, content: str) -> None:
    if not content:
        return
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="实验三：tPBFT 并行 Merkle Hash（真实交易）")
    parser.add_argument("--k", type=str, default="1,2,4,8")
    parser.add_argument("--tx", type=str, default="1000,5000,10000")
    parser.add_argument("--repeat", type=int, default=30)
    parser.add_argument("--nodes", type=int, default=1)
    parser.add_argument("--out", type=str, default="experiments/exp3_parallel_merkle/report")
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

    k_list = parse_list(args.k)
    tx_list = parse_list(args.tx)
    loadgen_args = shlex.split(args.loadgen_args)
    runner = ExperimentRunner(project_root=project_root)
    node_manager = NodeManager(project_root)

    points: List[ExperimentPoint] = []
    for tx_count in tx_list:
        for k in k_list:
            os.environ["CONSENSUS_ENGINE"] = "tpbft-parallel-block"
            os.environ["MERKLE_K"] = str(k)

            params = {"tx": tx_count, "k": k, "nodes": args.nodes}
            run_block_ms: List[float] = []
            run_confirm_ms: List[float] = []
            run_duration_s: List[float] = []
            run_cpu_percent: List[float] = []
            run_mem_bytes: List[float] = []
            run_net_mbps: List[float] = []
            run_io_util: List[float] = []
            run_tps: List[float] = []
            successful_runs = 0

            for run_index in range(args.repeat):
                run_data_root = artifact_root / f"data_tx_{tx_count}" / f"k_{k}" / f"run_{run_index + 1}"
                run_log_root = artifact_root / f"logs_tx_{tx_count}" / f"k_{k}" / f"run_{run_index + 1}"
                run_data_root.mkdir(parents=True, exist_ok=True)
                run_log_root.mkdir(parents=True, exist_ok=True)

                node_manager.start_nodes(args.nodes, run_data_root, run_log_root, use_cpu_affinity=True)
                monitor = SystemMonitor()
                monitor.start()

                expanded_args: List[str] = []
                for arg in loadgen_args:
                    value = arg.replace("{data_root}", str(run_data_root))
                    for key, val in params.items():
                        value = value.replace(f"{{{key}}}", str(val))
                    expanded_args.append(value)

                runner.wait_for_endpoint(expanded_args)
                duration_s, loadgen_snapshot = runner.trigger_loadgen(expanded_args)
                cpu_percent, mem_bytes, net_mbps, io_util, _, _, _ = monitor.stop()

                block_times = parse_block_times(run_log_root)
                confirm_times = parse_confirm_times(run_log_root)
                avg_block = avg(block_times)
                avg_confirm = avg(confirm_times)
                actual_tps = 0.0
                if isinstance(loadgen_snapshot, dict):
                    actual_tps = float(loadgen_snapshot.get("actual_tps", 0.0))

                run_block_ms.append(avg_block)
                run_confirm_ms.append(avg_confirm)
                run_duration_s.append(duration_s)
                run_cpu_percent.append(cpu_percent)
                run_mem_bytes.append(mem_bytes)
                run_net_mbps.append(net_mbps)
                run_io_util.append(io_util)
                run_tps.append(actual_tps)
                if avg_block > 0:
                    successful_runs += 1

                node_manager.stop_nodes()
                time.sleep(2)

            avg_block_ms = avg_nonzero(run_block_ms)
            avg_confirm_ms = avg_nonzero(run_confirm_ms)
            avg_duration_s = avg_nonzero(run_duration_s)
            avg_cpu_percent = avg_nonzero(run_cpu_percent)
            avg_mem_bytes = avg_nonzero(run_mem_bytes)
            avg_net_mbps = avg_nonzero(run_net_mbps)
            avg_io_util = avg_nonzero(run_io_util)
            avg_tps = avg_nonzero(run_tps)

            points.append(
                ExperimentPoint(
                    params={"tx": tx_count, "k": k, "nodes": args.nodes},
                    metrics={
                        "block_time_ms": avg_block_ms,
                        "avg_confirm_time_ms": avg_confirm_ms,
                        "duration_s": avg_duration_s,
                        "cpu_percent": avg_cpu_percent,
                        "mem_bytes": avg_mem_bytes,
                        "net_mbps": avg_net_mbps,
                        "io_util": avg_io_util,
                        "tps": avg_tps,
                        "successful_runs": successful_runs,
                    },
                )
            )

    for tx_count in tx_list:
        base = next(
            (p.metrics["block_time_ms"] for p in points if p.params["tx"] == tx_count and p.params["k"] == 1),
            0.0,
        )
        for point in points:
            if point.params["tx"] != tx_count:
                continue
            k = int(point.params["k"])
            t_block = float(point.metrics.get("block_time_ms", 0.0))
            speedup = base / t_block if base > 0 and t_block > 0 else 0.0
            efficiency = speedup / k if k > 0 else 0.0
            point.metrics["speedup"] = speedup
            point.metrics["efficiency"] = efficiency

    figures = []
    for tx_count in tx_list:
        ks = [k for k in k_list]
        times = [
            float(
                next(
                    p.metrics["block_time_ms"]
                    for p in points
                    if p.params["tx"] == tx_count and p.params["k"] == k
                )
            )
            for k in ks
        ]
        speedups = [
            float(
                next(
                    p.metrics["speedup"]
                    for p in points
                    if p.params["tx"] == tx_count and p.params["k"] == k
                )
            )
            for k in ks
        ]
        efficiencies = [
            float(
                next(
                    p.metrics["efficiency"]
                    for p in points
                    if p.params["tx"] == tx_count and p.params["k"] == k
                )
            )
            for k in ks
        ]
        charts = [
            (f"tblock_tx{tx_count}.svg", f"T_block vs k (tx={tx_count})", "k", "T_block(ms)", ks, times),
            (f"speedup_tx{tx_count}.svg", f"Speedup vs k (tx={tx_count})", "k", "Speedup", ks, speedups),
            (f"efficiency_tx{tx_count}.svg", f"Efficiency vs k (tx={tx_count})", "k", "Efficiency", ks, efficiencies),
        ]
        for filename, title, x_label, y_label, xs, ys in charts:
            svg = line_chart_svg([float(x) for x in xs], [float(y) for y in ys], title, x_label, y_label)
            path = figures_dir / filename
            write_svg(path, svg)
            figures.append(str(path.relative_to(output_dir)))
    append_tps_vs_tx_by_nodes_chart(
        figures=figures,
        points=points,
        output_dir=output_dir,
        figures_dir=figures_dir,
        line_figure_name="exp3_tps_vs_tx_by_nodes.svg",
        bar_figure_name="exp3_tps_vs_tx_by_nodes_bar.svg",
        title="实验3 性能曲线（TPS）",
        line_chart=parse_bool_flag(args.line_chart, True),
        bar_chart=parse_bool_flag(args.bar_chart, True),
    )

    summary_lines = [
        f"重复次数: {args.repeat}",
        f"节点数: {args.nodes}",
        "明细:",
    ]
    for point in points:
        tx = int(point.params.get("tx", 0))
        k = int(point.params.get("k", 1))
        summary_lines.append(
            "交易数:{tx} k:{k} 有效重复:{runs} T_block(ms):{t:.4f} Speedup:{s:.4f} Efficiency:{e:.4f} CPU(%):{cpu:.2f} Mem(bytes):{mem:.0f}".format(
                tx=tx,
                k=k,
                runs=int(point.metrics.get("successful_runs", 0)),
                t=float(point.metrics.get("block_time_ms", 0.0)),
                s=float(point.metrics.get("speedup", 0.0)),
                e=float(point.metrics.get("efficiency", 0.0)),
                cpu=float(point.metrics.get("cpu_percent", 0.0)),
                mem=float(point.metrics.get("mem_bytes", 0.0)),
            )
        )
    summary = "\n".join(summary_lines)

    result = ExperimentResult(
        name="实验三：tPBFT 并行 Merkle Hash（真实交易）",
        description="tPBFT 下真实交易列表的子块并行 Merkle 计算",
        points=points,
        metadata={
            "k_list": k_list,
            "tx_list": tx_list,
            "repeat": args.repeat,
            "nodes": args.nodes,
        },
    )
    result_path = output_dir / "result.json"
    runner.save_result(result_path, result)
    export_pdf(
        template_path=lab_root / "report" / "template.tex",
        output_dir=output_dir,
        title="实验三报告",
        summary=summary,
        figures=[],
    )
    export_markdown(
        output_dir=output_dir,
        title="实验三报告",
        summary=summary,
        figures=figures,
    )


if __name__ == "__main__":
    main()
