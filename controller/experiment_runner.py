import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

from controller.node_manager import NodeManager
from collector.log_parser import parse_block_times, parse_confirm_times
from collector.system_monitor import SystemMonitor
from analysis.latency import percentiles


@dataclass
class ExperimentPoint:
    params: Dict[str, Any]
    metrics: Dict[str, float]


@dataclass
class ExperimentResult:
    name: str
    description: str
    points: List[ExperimentPoint]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExperimentRunner:
    def __init__(
        self,
        project_root: Path,
        loadgen_bin: Optional[Path] = None,
    ) -> None:
        self.project_root = project_root
        self.node_manager = NodeManager(project_root)
        self.loadgen_bin = loadgen_bin or project_root / "hcp-loadgen" / "target" / "release" / "hcp-loadgen"

    def run(
        self,
        name: str,
        description: str,
        matrix: List[Dict[str, Any]],
        data_root: Path,
        log_root: Path,
        loadgen_args: List[str],
    ) -> ExperimentResult:
        points: List[ExperimentPoint] = []
        for params in matrix:
            num_nodes = int(params.get("nodes", 4))
            log_dir = log_root / f"nodes_{num_nodes}"
            data_dir = data_root / f"nodes_{num_nodes}"
            log_dir.mkdir(parents=True, exist_ok=True)
            self.node_manager.start_nodes(num_nodes, data_dir, log_dir, use_cpu_affinity=True)

            monitor = SystemMonitor()
            monitor.start()

            duration_s = self.trigger_loadgen(loadgen_args)

            cpu_percent, mem_bytes = monitor.stop()

            block_times = parse_block_times(log_dir)
            confirm_times = parse_confirm_times(log_dir)
            avg_block = sum(block_times) / len(block_times) if block_times else 0.0
            avg_confirm = sum(confirm_times) / len(confirm_times) if confirm_times else 0.0
            latency_stats = percentiles(confirm_times, [50, 95, 99])

            metrics = {
                "duration_s": duration_s,
                "avg_block_time_ms": avg_block,
                "avg_confirm_time_ms": avg_confirm,
                "p50_ms": latency_stats.get(50, 0.0),
                "p95_ms": latency_stats.get(95, 0.0),
                "p99_ms": latency_stats.get(99, 0.0),
                "cpu_percent": cpu_percent,
                "mem_bytes": mem_bytes,
            }
            points.append(ExperimentPoint(params=params, metrics=metrics))

            self.node_manager.stop_nodes()
            time.sleep(2)
        return ExperimentResult(name=name, description=description, points=points)

    def trigger_loadgen(self, extra_args: List[str]) -> float:
        if not self.loadgen_bin.exists():
            raise RuntimeError("未找到 loadgen 可执行文件")
        start = time.time()
        subprocess.run([str(self.loadgen_bin), *extra_args], cwd=str(self.project_root))
        return time.time() - start

    def save_result(self, path: Path, result: ExperimentResult) -> None:
        data = {
            "name": result.name,
            "description": result.description,
            "points": [
                {"params": p.params, "metrics": p.metrics} for p in result.points
            ],
            "metadata": result.metadata,
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
