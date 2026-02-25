import csv
import json
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

from controller.node_manager import NodeManager
from collector.log_parser import (
    parse_block_times,
    parse_confirm_times,
    parse_rocksdb_times,
    parse_rocksdb_compactions,
    parse_rocksdb_level0_files,
    parse_rocksdb_stall_micros,
    parse_rocksdb_wal_bytes,
    parse_rocksdb_wal_file_bytes,
    parse_rocksdb_wal_synced,
    parse_rocksdb_write_amplification,
    parse_consensus_failures,
)
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
        total_points = len(matrix)
        print(f"实验开始: {name}", flush=True)
        print(f"实验描述: {description}", flush=True)
        print(f"实验点数: {total_points}", flush=True)
        for index, params in enumerate(matrix, start=1):
            num_nodes = int(params.get("nodes", 4))
            tx_count = int(params.get("tx", 0))
            share_size_value = params.get("share_size") or params.get("share") or params.get("storage_group_size")
            print(f"[进度 {index}/{total_points}] 启动节点: {num_nodes}, 交易数: {tx_count}", flush=True)
            log_dir = log_root / f"nodes_{num_nodes}"
            data_dir = data_root / f"nodes_{num_nodes}"
            log_dir.mkdir(parents=True, exist_ok=True)
            if share_size_value:
                self.node_manager.start_nodes(
                    num_nodes,
                    data_dir,
                    log_dir,
                    use_cpu_affinity=True,
                    storage_group_size=int(share_size_value),
                )
            else:
                self.node_manager.start_nodes(num_nodes, data_dir, log_dir, use_cpu_affinity=True)

            monitor = SystemMonitor()
            monitor.start()

            expanded_args: List[str] = []
            for arg in loadgen_args:
                value = arg
                for key, val in params.items():
                    value = value.replace(f"{{{key}}}", str(val))
                expanded_args.append(value)

            print(f"[进度 {index}/{total_points}] 等待负载端点可用...", flush=True)
            self.wait_for_endpoint(expanded_args)

            print(f"[进度 {index}/{total_points}] 开始负载生成...", flush=True)
            duration_s, loadgen_snapshot = self.trigger_loadgen(expanded_args)
            print(f"[进度 {index}/{total_points}] 负载生成完成, 耗时: {duration_s:.2f}s", flush=True)

            cpu_percent, mem_bytes, net_mbps, io_util, io_await, io_read_s, io_write_s = monitor.stop()

            block_times = parse_block_times(log_dir)
            confirm_times = parse_confirm_times(log_dir)
            rocksdb_times = parse_rocksdb_times(log_dir)
            wal_sync_times = parse_rocksdb_wal_synced(log_dir)
            wal_bytes = parse_rocksdb_wal_bytes(log_dir)
            wal_file_bytes = parse_rocksdb_wal_file_bytes(log_dir)
            rocksdb_write_amp = parse_rocksdb_write_amplification(log_dir)
            rocksdb_l0_files = parse_rocksdb_level0_files(log_dir)
            rocksdb_compactions = parse_rocksdb_compactions(log_dir)
            rocksdb_stall = parse_rocksdb_stall_micros(log_dir)
            consensus_failures = parse_consensus_failures(log_dir)
            avg_block = sum(block_times) / len(block_times) if block_times else 0.0
            avg_confirm = sum(confirm_times) / len(confirm_times) if confirm_times else 0.0
            latency_stats = percentiles(confirm_times, [50, 95, 99]) if confirm_times else {}
            rocksdb_stats = percentiles(rocksdb_times, [50, 95, 99]) if rocksdb_times else {}
            avg_rocksdb = sum(rocksdb_times) / len(rocksdb_times) if rocksdb_times else 0.0
            avg_wal_sync = sum(wal_sync_times) / len(wal_sync_times) if wal_sync_times else 0.0
            avg_wal_bytes = sum(wal_bytes) / len(wal_bytes) if wal_bytes else 0.0
            avg_wal_file_bytes = sum(wal_file_bytes) / len(wal_file_bytes) if wal_file_bytes else 0.0
            avg_write_amp = sum(rocksdb_write_amp) / len(rocksdb_write_amp) if rocksdb_write_amp else 0.0
            avg_l0_files = sum(rocksdb_l0_files) / len(rocksdb_l0_files) if rocksdb_l0_files else 0.0
            avg_compaction_ms = (
                sum(rocksdb_compactions) / len(rocksdb_compactions) / 1000.0 if rocksdb_compactions else 0.0
            )
            avg_stall_ms = sum(rocksdb_stall) / len(rocksdb_stall) / 1000.0 if rocksdb_stall else 0.0

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
                "rocksdb_write_amplification": avg_write_amp,
                "rocksdb_compaction_ms": avg_compaction_ms,
                "rocksdb_level0_files": avg_l0_files,
                "rocksdb_stall_ms": avg_stall_ms,
                "rocksdb_wal_synced": avg_wal_sync,
                "rocksdb_wal_bytes": avg_wal_bytes,
                "rocksdb_wal_file_bytes": avg_wal_file_bytes,
                "cpu_percent": cpu_percent,
                "mem_bytes": mem_bytes,
                "net_mbps": net_mbps,
                "io_util": io_util,
                "io_await": io_await,
                "io_read_s": io_read_s,
                "io_write_s": io_write_s,
                "consensus_failures": float(consensus_failures),
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

            print(
                f"[进度 {index}/{total_points}] 采集完成: 节点={num_nodes} 交易={tx_count} "
                f"TPS={metrics.get('tps', 0.0):.2f} P99(ms)={metrics.get('p99_ms', 0.0):.2f}",
                flush=True,
            )
            self.node_manager.stop_nodes()
            time.sleep(2)
        print("实验完成", flush=True)
        return ExperimentResult(name=name, description=description, points=points)

    def wait_for_endpoint(self, args: List[str], timeout: int = 120) -> None:
        endpoint = self.extract_endpoint(args)
        if not endpoint:
            return
        parsed = urlparse(endpoint)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port
        if port is None:
            return
        start = time.time()
        while time.time() - start < timeout:
            try:
                with socket.create_connection((host, port), timeout=2):
                    return
            except OSError:
                time.sleep(1)
        raise RuntimeError("等待负载生成端点超时")

    def extract_endpoint(self, args: List[str]) -> Optional[str]:
        for key in ("--grpc-endpoint", "--http-endpoint"):
            if key in args:
                index = args.index(key)
                if index + 1 < len(args):
                    return args[index + 1]
        return None

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
        if last_snapshot is None:
            csv_path = self.extract_csv_path(extra_args)
            if csv_path:
                last_snapshot = self.read_csv_snapshot(Path(csv_path))
        return time.time() - start, last_snapshot

    def extract_csv_path(self, args: List[str]) -> Optional[str]:
        if "--csv-path" in args:
            index = args.index("--csv-path")
            if index + 1 < len(args):
                return args[index + 1]
        return None

    def read_csv_snapshot(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        last_row: Optional[Dict[str, str]] = None
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                last_row = row
        if not last_row:
            return None
        parsed: Dict[str, Any] = {}
        for key, value in last_row.items():
            if value is None or value == "":
                continue
            if key in {"sent", "success", "reject", "mem_bytes"}:
                parsed[key] = float(value)
            else:
                parsed[key] = float(value)
        return parsed

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
