import argparse
import hashlib
import os
import statistics
import time
from dataclasses import dataclass
from multiprocessing import current_process, get_context
from pathlib import Path
from typing import Dict, List, Tuple

from analysis.svg_chart import line_chart_svg
from collector.system_monitor import SystemMonitor
from controller.cpu_affinity import available_cores
from controller.experiment_runner import ExperimentPoint, ExperimentResult, ExperimentRunner
from report.exporter import export_markdown, export_pdf


def parse_list(value: str) -> List[int]:
    return [int(v.strip()) for v in value.split(",") if v.strip()]


def make_tx_bytes(count: int, size: int) -> List[bytes]:
    payloads: List[bytes] = []
    for i in range(count):
        seed = hashlib.sha256(str(i).encode("utf-8")).digest()
        if size <= len(seed):
            payloads.append(seed[:size])
        else:
            repeat = (size + len(seed) - 1) // len(seed)
            payloads.append((seed * repeat)[:size])
    return payloads


def hash_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def merkle_root_from_hashes(hashes: List[bytes]) -> bytes:
    if not hashes:
        return b""
    current = list(hashes)
    while len(current) > 1:
        if len(current) % 2 == 1:
            current.append(current[-1])
        next_level = []
        for i in range(0, len(current), 2):
            next_level.append(hash_bytes(current[i] + current[i + 1]))
        current = next_level
    return current[0]


def merkle_root_from_txs(txs: List[bytes]) -> bytes:
    leaf_hashes = [hash_bytes(tx) for tx in txs]
    return merkle_root_from_hashes(leaf_hashes)


def init_worker(cores: List[int]) -> None:
    identity = getattr(current_process(), "_identity", ())
    index = identity[0] - 1 if identity else 0
    if cores:
        core = cores[index % len(cores)]
        os.sched_setaffinity(0, {core})


def split_blocks(txs: List[bytes], k: int) -> List[List[bytes]]:
    total = len(txs)
    base = total // k
    remainder = total % k
    blocks = []
    start = 0
    for idx in range(k):
        size = base + (1 if idx < remainder else 0)
        end = start + size
        blocks.append(txs[start:end])
        start = end
    return blocks


@dataclass
class RunMetrics:
    total_ms: float
    sub_ms: float
    merge_ms: float
    cpu_percent: float
    mem_bytes: float
    io_util: float


def run_once(txs: List[bytes], k: int, pool, cores: List[int]) -> RunMetrics:
    monitor = SystemMonitor()
    monitor.start()
    start_total = time.perf_counter()
    start_sub = time.perf_counter()
    if k == 1:
        sub_roots = [merkle_root_from_txs(txs)]
    else:
        blocks = split_blocks(txs, k)
        sub_roots = pool.map(merkle_root_from_txs, blocks)
    end_sub = time.perf_counter()
    merge_root = merkle_root_from_hashes(list(sub_roots))
    _ = merge_root
    end_total = time.perf_counter()
    cpu_percent, mem_bytes, _, io_util, _, _, _ = monitor.stop()
    total_ms = (end_total - start_total) * 1000.0
    sub_ms = (end_sub - start_sub) * 1000.0
    merge_ms = max(total_ms - sub_ms, 0.0)
    return RunMetrics(
        total_ms=total_ms,
        sub_ms=sub_ms,
        merge_ms=merge_ms,
        cpu_percent=cpu_percent,
        mem_bytes=mem_bytes,
        io_util=io_util,
    )


def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: List[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def write_svg(path: Path, content: str) -> None:
    if not content:
        return
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="实验三：子块并行 Merkle Hash")
    parser.add_argument("--k", type=str, default="1,2,4,8")
    parser.add_argument("--tx", type=str, default="1000,5000,10000")
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--repeat", type=int, default=30)
    parser.add_argument("--out", type=str, default="experiments/exp3_parallel_merkle/report")
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
    data_root = artifact_root / "data"
    data_root.mkdir(parents=True, exist_ok=True)

    k_list = parse_list(args.k)
    tx_list = parse_list(args.tx)
    cores = available_cores()

    points: List[ExperimentPoint] = []
    p_estimates: Dict[int, float] = {}

    for tx_count in tx_list:
        txs = make_tx_bytes(tx_count, args.size)
        avg_by_k: Dict[int, float] = {}
        sub_by_k: Dict[int, float] = {}
        for k in k_list:
            totals: List[float] = []
            subs: List[float] = []
            merges: List[float] = []
            cpu_samples: List[float] = []
            mem_samples: List[float] = []
            io_samples: List[float] = []
            ctx = get_context("fork")
            pool = None
            if k > 1:
                pool = ctx.Pool(processes=k, initializer=init_worker, initargs=(cores,))
            try:
                for _ in range(args.repeat):
                    metrics = run_once(txs, k, pool, cores)
                    totals.append(metrics.total_ms)
                    subs.append(metrics.sub_ms)
                    merges.append(metrics.merge_ms)
                    cpu_samples.append(metrics.cpu_percent)
                    mem_samples.append(metrics.mem_bytes)
                    io_samples.append(metrics.io_util)
            finally:
                if pool:
                    pool.close()
                    pool.join()
            avg_total = avg(totals)
            avg_sub = avg(subs)
            avg_merge = avg(merges)
            avg_cpu = avg(cpu_samples)
            avg_mem = avg(mem_samples)
            avg_io = avg(io_samples)
            std_total = stdev(totals)
            std_sub = stdev(subs)
            std_merge = stdev(merges)
            avg_by_k[k] = avg_total
            sub_by_k[k] = avg_sub
            points.append(
                ExperimentPoint(
                    params={"tx": tx_count, "k": k, "size_bytes": args.size},
                    metrics={
                        "block_time_avg_ms": avg_total,
                        "block_time_std_ms": std_total,
                        "sub_time_avg_ms": avg_sub,
                        "sub_time_std_ms": std_sub,
                        "merge_time_avg_ms": avg_merge,
                        "merge_time_std_ms": std_merge,
                        "cpu_percent": avg_cpu,
                        "mem_bytes": avg_mem,
                        "io_util": avg_io,
                    },
                )
            )
        base_time = avg_by_k.get(1, 0.0)
        if base_time > 0:
            p_estimates[tx_count] = sub_by_k.get(1, 0.0) / base_time
        for point in points:
            if int(point.params.get("tx", 0)) != tx_count:
                continue
            k = int(point.params.get("k", 1))
            avg_time = float(point.metrics.get("block_time_avg_ms", 0.0))
            speedup = base_time / avg_time if avg_time > 0 and base_time > 0 else 0.0
            efficiency = speedup / k if k > 0 else 0.0
            point.metrics["speedup"] = speedup
            point.metrics["efficiency"] = efficiency
            p = p_estimates.get(tx_count, 0.0)
            point.metrics["amdahl_p"] = p
            if p > 0 and k > 0:
                point.metrics["amdahl_speedup"] = 1.0 / ((1 - p) + p / k)
            else:
                point.metrics["amdahl_speedup"] = 0.0

    result = ExperimentResult(
        name="实验三：子块并行 Merkle Hash",
        description="子块并行计算 Merkle 子树的吞吐与加速比评估",
        points=points,
        metadata={
            "k_list": k_list,
            "tx_list": tx_list,
            "tx_size_bytes": args.size,
            "repeat": args.repeat,
            "p_estimates": p_estimates,
        },
    )
    result_path = output_dir / "result.json"
    ExperimentRunner(project_root=project_root).save_result(result_path, result)

    figures = []
    for tx_count in tx_list:
        ks = [k for k in k_list]
        times = [
            float(
                next(
                    p.metrics["block_time_avg_ms"]
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
        "P估计:",
    ]
    for tx_count in tx_list:
        summary_lines.append(f"交易数:{tx_count} P:{p_estimates.get(tx_count, 0.0):.4f}")
    summary_lines.append("明细:")
    for point in points:
        tx = int(point.params.get("tx", 0))
        k = int(point.params.get("k", 1))
        summary_lines.append(
            "交易数:{tx} k:{k} T_block(ms):{t:.4f} Speedup:{s:.4f} Efficiency:{e:.4f} CPU(%):{cpu:.2f} Mem(bytes):{mem:.0f}".format(
                tx=tx,
                k=k,
                t=float(point.metrics.get("block_time_avg_ms", 0.0)),
                s=float(point.metrics.get("speedup", 0.0)),
                e=float(point.metrics.get("efficiency", 0.0)),
                cpu=float(point.metrics.get("cpu_percent", 0.0)),
                mem=float(point.metrics.get("mem_bytes", 0.0)),
            )
        )
    summary = "\n".join(summary_lines)
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
