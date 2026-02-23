import argparse
from pathlib import Path
from typing import List

from controller.experiment_runner import ExperimentRunner
from controller.param_matrix import build_matrix, load_matrix
from analysis.latency import percentiles
from analysis.tps import compute_tps
from analysis.probability import failure_curve
from analysis.storage_model import write_amplification
from visualization.plot_tps import plot_tps
from visualization.plot_latency import plot_latency
from visualization.plot_scaling import plot_scaling
from visualization.plot_security import plot_security
from report.exporter import export_pdf


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

    project_root = Path("/home/hcp-dev/hcp-project")
    output_dir = project_root / "hcp-lab" / args.out
    output_dir.mkdir(parents=True, exist_ok=True)

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
        data_root=project_root / ".hcp_lab_data",
        log_root=project_root / "logs" / "hcp_lab",
        loadgen_args=loadgen_args,
    )

    for point in result.points:
        tx_count = int(point.params.get("tx", 0))
        duration_s = point.metrics.get("duration_s", 0.0)
        tps = point.metrics.get("tps", 0.0)
        if tps <= 0.0 and tx_count > 0 and duration_s > 0.0:
            point.metrics["tps"] = compute_tps(tx_count, duration_s)

    result_path = output_dir / "result.json"
    runner.save_result(result_path, result)

    tps_points = [
        (float(p.params.get("nodes", 0)), p.metrics.get("tps", 0.0)) for p in result.points
    ]
    latency_points = [
        (float(p.params.get("nodes", 0)), p.metrics.get("avg_confirm_time_ms", 0.0))
        for p in result.points
    ]
    plot_tps(tps_points, output_dir / "tps.svg")
    plot_latency(latency_points, output_dir / "latency.svg")

    scaling_points = []
    for point in result.points:
        nodes = float(point.params.get("nodes", 1))
        tps = point.metrics.get("tps", 0.0)
        baseline = result.points[0].metrics.get("tps", 1.0)
        scaling_points.append((nodes, tps / baseline if baseline else 0.0))
    plot_scaling(scaling_points, output_dir / "scaling.svg")

    security_points = list(
        zip(parse_list(args.nodes), failure_curve(parse_list(args.nodes), 0.2))
    )
    plot_security([(float(x), y) for x, y in security_points], output_dir / "security.svg")

    rocksdb_all = [
        p.metrics.get("rocksdb_write_avg_ms", 0.0)
        for p in result.points
        if "rocksdb_write_avg_ms" in p.metrics
    ]
    avg_rocksdb = sum(rocksdb_all) / len(rocksdb_all) if rocksdb_all else 0.0

    summary_lines = [
        f"实验点数: {len(result.points)}",
        f"平均 RocksDB 写延迟: {avg_rocksdb:.2f} ms",
        f"写放大估计: {write_amplification(4096, 4 * 1024 * 1024):.2f}",
    ]
    summary = "\n".join(summary_lines)
    export_pdf(
        template_path=project_root / "hcp-lab" / "report" / "template.tex",
        output_dir=output_dir,
        title="HCP 实验报告",
        summary=summary,
        figures=["tps.svg", "latency.svg", "scaling.svg", "security.svg"],
    )


if __name__ == "__main__":
    main()
