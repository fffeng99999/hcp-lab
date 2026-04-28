import argparse
import os
import shlex
from pathlib import Path
from typing import List

from analysis.common_charts import append_tps_vs_tx_by_nodes_chart, parse_bool_flag
from controller.experiment_runner import ExperimentRunner
from controller.param_matrix import build_matrix, load_matrix
from analysis.tps import compute_tps
from analysis.storage_model import write_amplification
from report.exporter import export_markdown, export_pdf


def parse_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="实验一：交易量 × 节点规模")
    parser.add_argument("--matrix", type=str, help="参数矩阵 JSON 文件路径")
    parser.add_argument("--nodes", type=str, default="4,8,16,32")
    parser.add_argument("--tx", type=str, default="100,1000,10000")
    parser.add_argument("--out", type=str, default="experiments/exp1_tx_nodes/report")
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
    data_root = artifact_root / "data"
    log_root = artifact_root / "logs"
    data_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    print(f"输出目录: {output_dir}", flush=True)
    print(f"实验数据目录: {data_root}", flush=True)
    print(f"实验日志目录: {log_root}", flush=True)

    if args.matrix:
        matrix = load_matrix(Path(args.matrix))
    else:
        matrix = build_matrix(
            {
                "nodes": parse_list(args.nodes),
                "tx": parse_list(args.tx),
            }
        )

    loadgen_args = [arg.replace("{data_root}", str(data_root)) for arg in shlex.split(args.loadgen_args)]
    print(f"实验矩阵: {matrix}", flush=True)
    runner = ExperimentRunner(project_root=project_root)
    result = runner.run(
        name="实验一：交易量 × 节点规模",
        description="交易量与节点规模组合实验",
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
    print(f"结果已保存: {result_path}", flush=True)

    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    figures: List[str] = []
    append_tps_vs_tx_by_nodes_chart(
        figures=figures,
        points=result.points,
        output_dir=output_dir,
        figures_dir=figures_dir,
        line_figure_name="exp1_tps_vs_tx_by_nodes.svg",
        bar_figure_name="exp1_tps_vs_tx_by_nodes_bar.svg",
        title="实验1 性能曲线（TPS）",
        line_chart=parse_bool_flag(args.line_chart, True),
        bar_chart=parse_bool_flag(args.bar_chart, True),
    )

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
        title="实验一报告",
        summary=summary,
        figures=[],
    )
    export_markdown(
        output_dir=output_dir,
        title="实验一报告",
        summary=summary,
        figures=figures,
    )
    print(f"报告已生成: {output_dir}", flush=True)


if __name__ == "__main__":
    main()
