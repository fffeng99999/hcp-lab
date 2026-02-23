import argparse
import os
from pathlib import Path
from typing import List

from controller.experiment_runner import ExperimentRunner
from controller.param_matrix import build_matrix, load_matrix
from analysis.latency import percentiles
from analysis.tps import compute_tps
from analysis.storage_model import write_amplification
from report.exporter import export_markdown, export_pdf


def parse_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="HCP 实验编排与分析系统")
    parser.add_argument("--matrix", type=str, help="参数矩阵 JSON 文件路径")
    parser.add_argument("--nodes", type=str, default="4,8")
    parser.add_argument("--tx", type=str, default="100,500")
    parser.add_argument("--out", type=str, default="outputs")
    parser.add_argument("--loadgen-args", type=str, default="")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
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
    data_root = artifact_root / "data"
    log_root = artifact_root / "logs"
    data_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)

    if args.matrix:
        matrix = load_matrix(Path(args.matrix))
    else:
        matrix = build_matrix(
            {
                "nodes": parse_list(args.nodes),
                "tx": parse_list(args.tx),
            }
        )

    loadgen_args = [item for item in args.loadgen_args.split(" ") if item]
    runner = ExperimentRunner(project_root=project_root)
    result = runner.run(
        name="HCP 实验",
        description="自动化实验矩阵",
        matrix=matrix,
        data_root=data_root,
        log_root=log_root,
        loadgen_args=loadgen_args,
    )

    for point in result.points:
        tx_count = int(point.params.get("tx", 0))
        duration_s = point.metrics.get("duration_s", 0.0)
        if "tps" not in point.metrics and tx_count > 0 and duration_s > 0.0:
            point.metrics["tps"] = compute_tps(tx_count, duration_s)

    result_path = output_dir / "result.json"
    runner.save_result(result_path, result)

    durations = [p.metrics.get("duration_s", 0.0) for p in result.points]
    avg_latencies = [p.metrics.get("avg_confirm_time_ms", 0.0) for p in result.points]
    p99_latencies = [p.metrics.get("p99_ms", 0.0) for p in result.points]
    cpu_usages = [p.metrics.get("cpu_percent", 0.0) for p in result.points]
    net_usages = [p.metrics.get("net_mbps", 0.0) for p in result.points]
    rocksdb_writes = [p.metrics.get("rocksdb_write_avg_ms", 0.0) for p in result.points]

    def avg(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    summary_lines = [
        f"实验点数: {len(result.points)}",
        f"平均完成时间(s): {avg(durations):.6f}",
        f"平均延迟(ms): {avg(avg_latencies):.6f}",
        f"平均P99延迟(ms): {avg(p99_latencies):.6f}",
        f"平均CPU使用率(%): {avg(cpu_usages):.6f}",
        f"平均网络带宽(Mbps): {avg(net_usages):.6f}",
        f"平均RocksDB写延迟(ms): {avg(rocksdb_writes):.6f}",
        f"写放大估计: {write_amplification(4096, 4 * 1024 * 1024):.2f}",
        "明细:",
    ]
    for point in result.points:
        nodes = int(point.params.get("nodes", 0))
        tx = int(point.params.get("tx", 0))
        summary_lines.append(
            "节点:{nodes} 交易数:{tx} 完成时间(s):{duration:.6f} 平均延迟(ms):{avg_latency:.6f} P99(ms):{p99:.6f} CPU(%):{cpu:.6f} 网络(Mbps):{net:.6f} RocksDB写延迟(ms):{rocksdb:.6f}".format(
                nodes=nodes,
                tx=tx,
                duration=float(point.metrics.get("duration_s", 0.0)),
                avg_latency=float(point.metrics.get("avg_confirm_time_ms", 0.0)),
                p99=float(point.metrics.get("p99_ms", 0.0)),
                cpu=float(point.metrics.get("cpu_percent", 0.0)),
                net=float(point.metrics.get("net_mbps", 0.0)),
                rocksdb=float(point.metrics.get("rocksdb_write_avg_ms", 0.0)),
            )
        )
    summary = "\n".join(summary_lines)
    export_pdf(
        template_path=lab_root / "report" / "template.tex",
        output_dir=output_dir,
        title="HCP 实验报告",
        summary=summary,
        figures=[],
    )
    export_markdown(
        output_dir=output_dir,
        title="HCP 实验报告",
        summary=summary,
    )


if __name__ == "__main__":
    main()
