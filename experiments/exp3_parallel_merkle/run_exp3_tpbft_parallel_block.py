import argparse
import os
import time
from pathlib import Path
from typing import List

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
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[3]
    lab_root = project_root / "hcp-lab"
    out_path = Path(args.out)
    output_dir = out_path if out_path.is_absolute() else lab_root / out_path
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
    loadgen_args = [item for item in args.loadgen_args.split(" ") if item]
    runner = ExperimentRunner(project_root=project_root)
    node_manager = NodeManager(project_root)

    points: List[ExperimentPoint] = []
    for tx_count in tx_list:
        for k in k_list:
            data_root = artifact_root / f"data_tx_{tx_count}" / f"k_{k}"
            log_root = artifact_root / f"logs_tx_{tx_count}" / f"k_{k}"
            data_root.mkdir(parents=True, exist_ok=True)
            log_root.mkdir(parents=True, exist_ok=True)
            os.environ["CONSENSUS_ENGINE"] = "tpbft-parallel-block"
            os.environ["MERKLE_K"] = str(k)

            node_manager.start_nodes(args.nodes, data_root, log_root, use_cpu_affinity=True)
            monitor = SystemMonitor()
            monitor.start()

            expanded_args: List[str] = []
            for arg in loadgen_args:
                value = (
                    arg.replace("{tx}", str(tx_count))
                    .replace("{k}", str(k))
                    .replace("{data_root}", str(data_root))
                )
                expanded_args.append(value)

            runner.wait_for_endpoint(expanded_args)
            duration_s, loadgen_snapshot = runner.trigger_loadgen(expanded_args)
            cpu_percent, mem_bytes, net_mbps, io_util, _, _, _ = monitor.stop()

            block_times = parse_block_times(log_root)
            confirm_times = parse_confirm_times(log_root)
            avg_block = avg(block_times)
            avg_confirm = avg(confirm_times)
            actual_tps = 0.0
            if isinstance(loadgen_snapshot, dict):
                actual_tps = float(loadgen_snapshot.get("actual_tps", 0.0))

            points.append(
                ExperimentPoint(
                    params={"tx": tx_count, "k": k, "nodes": args.nodes},
                    metrics={
                        "block_time_ms": avg_block,
                        "avg_confirm_time_ms": avg_confirm,
                        "duration_s": duration_s,
                        "cpu_percent": cpu_percent,
                        "mem_bytes": mem_bytes,
                        "net_mbps": net_mbps,
                        "io_util": io_util,
                        "tps": actual_tps,
                    },
                )
            )

            node_manager.stop_nodes()
            time.sleep(2)

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

    summary_lines = [
        f"重复次数: {args.repeat}",
        f"节点数: {args.nodes}",
        "明细:",
    ]
    for point in points:
        tx = int(point.params.get("tx", 0))
        k = int(point.params.get("k", 1))
        summary_lines.append(
            "交易数:{tx} k:{k} T_block(ms):{t:.4f} Speedup:{s:.4f} Efficiency:{e:.4f} CPU(%):{cpu:.2f} Mem(bytes):{mem:.0f}".format(
                tx=tx,
                k=k,
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
