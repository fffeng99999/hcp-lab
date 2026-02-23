import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional

from controller.node_manager import NodeManager
from collector.log_parser import parse_block_times, parse_confirm_times, parse_rocksdb_times
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

            expanded_args: List[str] = []
            for arg in loadgen_args:
                value = arg
                for key, val in params.items():
                    value = value.replace(f"{{{key}}}", str(val))
                expanded_args.append(value)

            duration_s, loadgen_snapshot = self.trigger_loadgen(expanded_args)

            cpu_percent, mem_bytes, net_mbps = monitor.stop()

            block_times = parse_block_times(log_dir)
            confirm_times = parse_confirm_times(log_dir)
            rocksdb_times = parse_rocksdb_times(log_dir)
            avg_block = sum(block_times) / len(block_times) if block_times else 0.0
            avg_confirm = sum(confirm_times) / len(confirm_times) if confirm_times else 0.0
            latency_stats = percentiles(confirm_times, [50, 95, 99]) if confirm_times else {}
            rocksdb_stats = percentiles(rocksdb_times, [50, 95, 99]) if rocksdb_times else {}
            avg_rocksdb = sum(rocksdb_times) / len(rocksdb_times) if rocksdb_times else 0.0

            metrics = {
                "duration_s": duration_s,
                "avg_block_time_ms": avg_block,
                "avg_confirm_time_ms": avg_confirm,
                "p50_ms": latency_stats.get(50, 0.0),
                "p95_ms": latency_stats.get(95, 0.0),
                "p99_ms": latency_stats.get(99, 0.0),
                "rocksdb_write_avg_ms": avg_rocksdb,
                "rocksdb_write_p50_ms": rocksdb_stats.get(50, 0.0),
                "rocksdb_write_p95_ms": rocksdb_stats.get(95, 0.0),
                "rocksdb_write_p99_ms": rocksdb_stats.get(99, 0.0),
                "cpu_percent": cpu_percent,
                "mem_bytes": mem_bytes,
                "net_mbps": net_mbps,
            }

            if isinstance(loadgen_snapshot, dict):
                elapsed_s = float(loadgen_snapshot.get("elapsed_s", duration_s))
                actual_tps = float(loadgen_snapshot.get("actual_tps", 0.0))
                latency_avg_ms = float(loadgen_snapshot.get("latency_avg_ms", 0.0))
                latency_p50_ms = float(loadgen_snapshot.get("latency_p50_ms", 0.0))
                latency_p90_ms = float(loadgen_snapshot.get("latency_p90_ms", 0.0))
                latency_p99_ms = float(loadgen_snapshot.get("latency_p99_ms", 0.0))
                cpu_percent_lg = float(loadgen_snapshot.get("cpu_percent", cpu_percent))
                mem_bytes_lg = float(loadgen_snapshot.get("mem_bytes", mem_bytes))

                metrics["duration_s"] = elapsed_s
                metrics["avg_confirm_time_ms"] = latency_avg_ms or metrics["avg_confirm_time_ms"]
                metrics["p50_ms"] = latency_p50_ms or metrics["p50_ms"]
                metrics["p95_ms"] = latency_p90_ms or metrics["p95_ms"]
                metrics["p99_ms"] = latency_p99_ms or metrics["p99_ms"]
                metrics["cpu_percent"] = cpu_percent_lg
                metrics["mem_bytes"] = mem_bytes_lg
                metrics["tps"] = actual_tps

            points.append(ExperimentPoint(params=params, metrics=metrics))

            self.node_manager.stop_nodes()
            time.sleep(2)
        return ExperimentResult(name=name, description=description, points=points)

    def trigger_loadgen(self, extra_args: List[str]) -> (float, Optional[Dict[str, Any]]):
        if not self.loadgen_bin.exists():
            raise RuntimeError("未找到 loadgen 可执行文件")
        start = time.time()
        process = subprocess.Popen(
            [str(self.loadgen_bin), *extra_args],
            cwd=str(self.project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        last_snapshot: Optional[Dict[str, Any]] = None
        if process.stdout is not None:
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and "actual_tps" in data:
                    last_snapshot = data
        process.wait()
        return time.time() - start, last_snapshot

    def save_result(self, path: Path, result: ExperimentResult) -> None:
        def _format_floats(obj: Any) -> Any:
            if isinstance(obj, float):
                return f"{obj:.16f}"
            if isinstance(obj, dict):
                return {k: _format_floats(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_format_floats(v) for v in obj]
            return obj

        data = {
            "name": result.name,
            "description": result.description,
            "points": [
                {"params": p.params, "metrics": p.metrics} for p in result.points
            ],
            "metadata": result.metadata,
        }
        formatted = _format_floats(data)
        path.write_text(json.dumps(formatted, ensure_ascii=False, indent=2), encoding="utf-8")
