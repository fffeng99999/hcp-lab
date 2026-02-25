import argparse
import os
import shlex
from pathlib import Path
from typing import Dict, List

from analysis.svg_chart import line_chart_svg
from controller.experiment_runner import ExperimentRunner
from report.exporter import export_markdown, export_pdf


def parse_list(value: str) -> List[int]:
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
    parser = argparse.ArgumentParser(description="实验二：共享存储规模变化对共识吞吐的影响")
    parser.add_argument("--shares", type=str, default="2,4,8,16")
    parser.add_argument("--nodes", type=int, default=32)
    parser.add_argument("--tx", type=int, default=10000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--out", type=str, default="experiments/exp2_storage_share/report")
    parser.add_argument("--loadgen-args", type=str, default="")
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

    share_sizes = parse_list(args.shares)
    runner = ExperimentRunner(project_root=project_root)
    base_loadgen_args = shlex.split(args.loadgen_args)

    aggregated: Dict[int, Dict[str, float]] = {}
    for share_size in share_sizes:
        samples: List[Dict[str, float]] = []
        for repeat_idx in range(1, args.repeat + 1):
            data_root = artifact_root / f"data_share_{share_size}" / f"run_{repeat_idx}"
            log_root = artifact_root / f"logs_share_{share_size}" / f"run_{repeat_idx}"
            data_root.mkdir(parents=True, exist_ok=True)
            log_root.mkdir(parents=True, exist_ok=True)
            matrix = [
                {
                    "nodes": args.nodes,
                    "tx": args.tx,
                    "share_size": share_size,
                }
            ]
            loadgen_args = [arg.replace("{data_root}", str(data_root)) for arg in base_loadgen_args]
            result = runner.run(
                name="实验二：共享存储规模变化对共识吞吐的影响",
                description="共享存储规模变化对共识吞吐与延迟影响",
                matrix=matrix,
                data_root=data_root,
                log_root=log_root,
                loadgen_args=loadgen_args,
            )
            if result.points:
                samples.append(result.points[0].metrics)
        aggregated[share_size] = aggregate_metrics(samples)

    share_sizes_sorted = sorted(aggregated.keys())
    tps_values = [aggregated[s].get("tps", 0.0) for s in share_sizes_sorted]
    wa_values = [aggregated[s].get("rocksdb_write_amplification", 0.0) for s in share_sizes_sorted]
    compaction_values = [aggregated[s].get("rocksdb_compaction_ms", 0.0) for s in share_sizes_sorted]
    commit_values = [aggregated[s].get("avg_confirm_time_ms", 0.0) for s in share_sizes_sorted]
    io_util_values = [aggregated[s].get("io_util", 0.0) for s in share_sizes_sorted]

    charts = [
        ("share_tps.svg", "共享规模 vs TPS", "每实例承载节点数", "TPS", share_sizes_sorted, tps_values),
        ("share_wa.svg", "共享规模 vs Write Amplification", "每实例承载节点数", "WA", share_sizes_sorted, wa_values),
        ("share_compaction.svg", "共享规模 vs Compaction 时间", "每实例承载节点数", "Compaction(ms)", share_sizes_sorted, compaction_values),
        ("share_commit.svg", "共享规模 vs Commit 延迟", "每实例承载节点数", "Commit(ms)", share_sizes_sorted, commit_values),
        ("share_ioutil.svg", "共享规模 vs IO util", "每实例承载节点数", "IO Util(%)", share_sizes_sorted, io_util_values),
    ]

    figures = []
    for filename, title, x_label, y_label, xs, ys in charts:
        svg = line_chart_svg([float(x) for x in xs], [float(y) for y in ys], title, x_label, y_label)
        path = figures_dir / filename
        write_svg(path, svg)
        figures.append(str(path.relative_to(output_dir)))

    summary_lines = [
        f"总节点数: {args.nodes}",
        f"交易数: {args.tx}",
        f"重复次数: {args.repeat}",
        "明细:",
    ]
    for share_size in share_sizes_sorted:
        metrics = aggregated[share_size]
        summary_lines.append(
            "共享规模:{share} TPS:{tps:.2f} Commit(ms):{commit:.2f} WA:{wa:.4f} Compaction(ms):{comp:.2f} IO Util(%):{io:.2f}".format(
                share=share_size,
                tps=float(metrics.get("tps", 0.0)),
                commit=float(metrics.get("avg_confirm_time_ms", 0.0)),
                wa=float(metrics.get("rocksdb_write_amplification", 0.0)),
                comp=float(metrics.get("rocksdb_compaction_ms", 0.0)),
                io=float(metrics.get("io_util", 0.0)),
            )
        )
    summary = "\n".join(summary_lines)

    export_pdf(
        template_path=lab_root / "report" / "template.tex",
        output_dir=output_dir,
        title="实验二报告",
        summary=summary,
        figures=[],
    )
    export_markdown(
        output_dir=output_dir,
        title="实验二报告",
        summary=summary,
        figures=figures,
    )


if __name__ == "__main__":
    main()
