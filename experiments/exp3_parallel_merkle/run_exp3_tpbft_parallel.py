import argparse
import os
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple

from analysis.svg_chart import line_chart_svg
from collector.system_monitor import SystemMonitor
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner
from controller.node_manager import NodeManager
from report.exporter import export_markdown, export_pdf


def parse_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def write_svg(path: Path, content: str) -> None:
    if not content:
        return
    path.write_text(content, encoding="utf-8")


def wait_for_metrics(log_file: Path, timeout: int = 120) -> Optional[Tuple[float, float, float]]:
    pattern = re.compile(
        r"block_time:\s*([\d.]+)\s*ms.*subblock_time:\s*([\d.]+)\s*ms.*merge_time:\s*([\d.]+)\s*ms"
    )
    start = time.time()
    while time.time() - start < timeout:
        if log_file.exists():
            lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in reversed(lines):
                match = pattern.search(line)
                if match:
                    return (
                        float(match.group(1)),
                        float(match.group(2)),
                        float(match.group(3)),
                    )
        time.sleep(0.5)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="实验三：tPBFT 并行 Merkle Hash")
    parser.add_argument("--k", type=str, default="1,2,4,8")
    parser.add_argument("--tx", type=str, default="1000,5000,10000")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--repeat", type=int, default=30)
    parser.add_argument("--nodes", type=int, default=1)
    parser.add_argument("--out", type=str, default="experiments/exp3_parallel_merkle/report")
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
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    k_list = parse_list(args.k)
    tx_list = parse_list(args.tx)

    points: List[ExperimentPoint] = []
    for tx_count in tx_list:
        for k in k_list:
            data_root = artifact_root / f"data_tx_{tx_count}" / f"k_{k}"
            log_root = artifact_root / f"logs_tx_{tx_count}" / f"k_{k}"
            data_root.mkdir(parents=True, exist_ok=True)
            log_root.mkdir(parents=True, exist_ok=True)
            os.environ["CONSENSUS_ENGINE"] = "tpbft-parallel"
            os.environ["MERKLE_TX_COUNT"] = str(tx_count)
            os.environ["MERKLE_TX_SIZE"] = str(args.size)
            os.environ["MERKLE_K"] = str(k)
            os.environ["MERKLE_REPEAT"] = str(args.repeat)

            node_manager = NodeManager(project_root)
            node_manager.start_nodes(args.nodes, data_root, log_root, use_cpu_affinity=True)
            monitor = SystemMonitor()
            monitor.start()
            log_file = log_root / "node1.log"
            metrics = wait_for_metrics(log_file)
            cpu_percent, mem_bytes, net_mbps, io_util, _, _, _ = monitor.stop()
            node_manager.stop_nodes()
            time.sleep(2)

            block_ms = metrics[0] if metrics else 0.0
            sub_ms = metrics[1] if metrics else 0.0
            merge_ms = metrics[2] if metrics else 0.0
            points.append(
                ExperimentPoint(
                    params={"tx": tx_count, "k": k, "size_bytes": args.size},
                    metrics={
                        "block_time_ms": block_ms,
                        "subblock_time_ms": sub_ms,
                        "merge_time_ms": merge_ms,
                        "cpu_percent": cpu_percent,
                        "mem_bytes": mem_bytes,
                        "net_mbps": net_mbps,
                        "io_util": io_util,
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

    summary_lines = [
        f"交易大小(Bytes): {args.size}",
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
        name="实验三：tPBFT 并行 Merkle Hash",
        description="tPBFT 下子块并行计算 Merkle 子树的吞吐与加速比评估",
        points=points,
        metadata={
            "k_list": k_list,
            "tx_list": tx_list,
            "tx_size_bytes": args.size,
            "repeat": args.repeat,
            "nodes": args.nodes,
        },
    )
    result_path = output_dir / "result.json"
    ExperimentRunner(project_root=project_root).save_result(result_path, result)
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
