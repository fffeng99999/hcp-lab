#!/usr/bin/env python3
"""公共实验运行工具"""
import json
import os
import subprocess
import statistics
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BENCH_BIN = PROJECT_ROOT / "hcp-consensus-build" / "hcp-bench"
TESTS_DIR = PROJECT_ROOT / "tests"


def run_benchmark(engine: str, nodes: int, txs: int, outdir: Path, suffix: str = "") -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / f"{engine}_n{nodes}_t{txs}{suffix}.json"
    cmd = [str(BENCH_BIN), "benchmark", engine, str(nodes), str(txs), str(outfile)]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if outfile.exists():
        return json.loads(outfile.read_text())
    return {}


def run_benchmark_group(engine: str, nodes: int, groups: int, txs: int, outdir: Path, suffix: str = "") -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = outdir / f"{engine}_g{groups}_n{nodes}_t{txs}{suffix}.json"
    cmd = [str(BENCH_BIN), "benchmark-group", engine, str(nodes), str(groups), str(txs), str(outfile)]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if outfile.exists():
        return json.loads(outfile.read_text())
    return {}


def avg(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    return statistics.stdev(values)


def sem(values: List[float]) -> float:
    """标准误"""
    if len(values) <= 1:
        return 0.0
    return statistics.stdev(values) / (len(values) ** 0.5)


def ci95(values: List[float]) -> tuple:
    """95%置信区间 (t分布近似，n>=5时t≈2.776 for df=4)"""
    if len(values) <= 1:
        return (0.0, 0.0)
    m = avg(values)
    s = sem(values)
    t = 2.776 if len(values) == 5 else (2.262 if len(values) == 10 else 2.0)
    margin = t * s
    return (m - margin, m + margin)


def format_stat(values: List[float]) -> str:
    """格式化统计量: mean±std [CI_lo, CI_hi]"""
    if not values:
        return "N/A"
    m = avg(values)
    s = stdev(values)
    lo, hi = ci95(values)
    return f"{m:.2f}±{s:.2f} [{lo:.2f}, {hi:.2f}]"


def copy_to_report(src_dir: Path, exp_name: str):
    dst_dir = PROJECT_ROOT / "hcp-lab" / "experiments" / exp_name / "report"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for f in src_dir.iterdir():
        if f.is_file():
            dst_dir.joinpath(f.name).write_text(f.read_text())


def save_json(data, path: Path):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def save_md(lines: List[str], path: Path):
    path.write_text("\n".join(lines))
