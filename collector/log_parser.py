import re
from pathlib import Path
from typing import List, Dict


BLOCK_PATTERNS = [
    re.compile(r"block[_\s]?time[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
    re.compile(r"block\s+latency[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
]

CONFIRM_PATTERNS = [
    re.compile(r"confirm[_\s]?time[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
    re.compile(r"tx\s+confirm[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
]

CONSENSUS_FAIL_PATTERNS = [
    re.compile(r"consensus.*fail", re.IGNORECASE),
    re.compile(r"commit.*fail", re.IGNORECASE),
    re.compile(r"panic", re.IGNORECASE),
]

HIERARCHICAL_METRICS_PATTERN = re.compile(
    r"hierarchical_metrics\s+pre_prepare_ms=([\d.]+)\s+prepare_ms=([\d.]+)\s+commit_ms=([\d.]+)\s+comm_bytes=([\d.]+)",
    re.IGNORECASE,
)

ROCKSDB_PATTERNS = [
    re.compile(r"rocksdb_write.*duration_ms[=:]\s*([\d.]+)", re.IGNORECASE),
    re.compile(r"rocksdb_write.*duration_ms\s*([\d.]+)", re.IGNORECASE),
]

ROCKSDB_STAT_KEYS = [
    "rocksdb.write.amplification",
    "rocksdb.compaction.times.micros",
    "rocksdb.num-files-at-level0",
    "rocksdb.stall.micros",
    "rocksdb.wal.synced",
    "rocksdb.wal.bytes",
    "rocksdb.wal.file.bytes",
]


def parse_block_times(log_dir: Path) -> List[float]:
    return _parse_patterns(log_dir, BLOCK_PATTERNS)


def parse_confirm_times(log_dir: Path) -> List[float]:
    return _parse_patterns(log_dir, CONFIRM_PATTERNS)


def parse_rocksdb_times(log_dir: Path) -> List[float]:
    values = _parse_patterns(log_dir, ROCKSDB_PATTERNS)
    if values:
        return values
    data_dir = log_dir.parent.parent / "data" / log_dir.name
    if data_dir.exists():
        values = _parse_rocksdb_log_files(data_dir)
    return values


def parse_rocksdb_write_amplification(log_dir: Path) -> List[float]:
    return _parse_rocksdb_stat(log_dir, "rocksdb.write.amplification")


def parse_rocksdb_compactions(log_dir: Path) -> List[float]:
    return _parse_rocksdb_stat(log_dir, "rocksdb.compaction.times.micros")


def parse_rocksdb_level0_files(log_dir: Path) -> List[float]:
    return _parse_rocksdb_stat(log_dir, "rocksdb.num-files-at-level0")


def parse_rocksdb_stall_micros(log_dir: Path) -> List[float]:
    return _parse_rocksdb_stat(log_dir, "rocksdb.stall.micros")


def parse_rocksdb_wal_synced(log_dir: Path) -> List[float]:
    return _parse_rocksdb_stat(log_dir, "rocksdb.wal.synced")


def parse_rocksdb_wal_bytes(log_dir: Path) -> List[float]:
    return _parse_rocksdb_stat(log_dir, "rocksdb.wal.bytes")


def parse_rocksdb_wal_file_bytes(log_dir: Path) -> List[float]:
    return _parse_rocksdb_stat(log_dir, "rocksdb.wal.file.bytes")


def parse_consensus_failures(log_dir: Path) -> int:
    return _count_patterns(log_dir, CONSENSUS_FAIL_PATTERNS)

def parse_hierarchical_metrics(log_dir: Path) -> Dict[str, List[float]]:
    pre_values: List[float] = []
    prepare_values: List[float] = []
    commit_values: List[float] = []
    comm_values: List[float] = []
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    for log_file in log_dir.glob("**/*.log"):
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean_line = ansi_pattern.sub("", line)
            match = HIERARCHICAL_METRICS_PATTERN.search(clean_line)
            if match:
                pre_values.append(float(match.group(1)))
                prepare_values.append(float(match.group(2)))
                commit_values.append(float(match.group(3)))
                comm_values.append(float(match.group(4)))
    return {
        "pre_prepare_ms": pre_values,
        "prepare_ms": prepare_values,
        "commit_ms": commit_values,
        "comm_bytes": comm_values,
    }


def parse_hierarchical_tpbft_metrics(log_dir: Path) -> Dict[str, List[float]]:
    metrics = {
        "pre_prepare_ms": [],
        "prepare_ms": [],
        "commit_ms": [],
        "comm_bytes": [],
        "total_messages": [],
        "sig_gen_count": [],
        "sig_verify_count": [],
        "sig_gen_time_ms": [],
        "sig_verify_time_ms": [],
        "aggregation_time_ms": [],
        "verify_time_ms": [],
        "sig_per_node": [],
        "sig_ops_per_tx": [],
        "batch_size": [],
        "batch_verify": [],
        "verify_gain": [],
        "sig_gen_parallelism": [],
        "sig_verify_parallelism": [],
        "sig_agg_parallelism": [],
    }
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    for log_file in log_dir.glob("**/*.log"):
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean_line = ansi_pattern.sub("", line)
            if "hierarchical_tpbft_metrics" not in clean_line:
                continue
            for part in clean_line.split():
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                if key not in metrics:
                    continue
                try:
                    metrics[key].append(float(value))
                except ValueError:
                    continue
    return metrics


def parse_votor_metrics(log_dir: Path) -> Dict[str, float]:
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    key_values: Dict[str, List[float]] = {
        "notarize_latency_ms": [],
        "finalize_latency_ms": [],
        "bls_agg_ms": [],
        "p2p_vote_bytes": [],
        "gossip_vote_bytes": [],
        "certificate_bytes": [],
    }
    path_counts: Dict[str, int] = {"fast": 0, "slow": 0, "fail": 0}

    notarize_patterns = [
        re.compile(r"notarize[_\s]?latency(?:_ms)?[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
        re.compile(r"notarization[_\s]?latency(?:_ms)?[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
    ]
    finalize_patterns = [
        re.compile(r"finalize[_\s]?latency(?:_ms)?[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
        re.compile(r"finality[_\s]?latency(?:_ms)?[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
    ]
    bls_patterns = [
        re.compile(r"bls[_\s]?(?:agg|aggregate|aggregation)[_\s]?ms[:=]\s*([\d.]+)", re.IGNORECASE),
        re.compile(r"certificate[_\s]?gen(?:_ms)?[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
    ]

    for log_file in log_dir.glob("**/*.log"):
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean_line = ansi_pattern.sub("", line)

            if "votor_metrics" in clean_line.lower():
                for part in clean_line.split():
                    if "=" not in part:
                        continue
                    key, value = part.split("=", 1)
                    key = key.strip().lower()
                    value = value.strip().lower()
                    if key in {"path", "path_type"}:
                        if value in path_counts:
                            path_counts[value] += 1
                        continue
                    if key in key_values:
                        try:
                            key_values[key].append(float(value))
                        except ValueError:
                            continue
                continue

            lower = clean_line.lower()
            if "votor" not in lower and "finality" not in lower and "notar" not in lower:
                continue

            for pattern in notarize_patterns:
                match = pattern.search(clean_line)
                if match:
                    key_values["notarize_latency_ms"].append(float(match.group(1)))
                    break
            for pattern in finalize_patterns:
                match = pattern.search(clean_line)
                if match:
                    key_values["finalize_latency_ms"].append(float(match.group(1)))
                    break
            for pattern in bls_patterns:
                match = pattern.search(clean_line)
                if match:
                    key_values["bls_agg_ms"].append(float(match.group(1)))
                    break

            if "fast-path" in lower or "fast_path" in lower or "path=fast" in lower:
                path_counts["fast"] += 1
            elif "slow-path" in lower or "slow_path" in lower or "path=slow" in lower:
                path_counts["slow"] += 1
            elif "path=fail" in lower or "votor_fail" in lower:
                path_counts["fail"] += 1

    def avg(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    def percentile(values: List[float], p: float) -> float:
        if not values:
            return 0.0
        if p <= 0:
            return min(values)
        if p >= 100:
            return max(values)
        values_sorted = sorted(values)
        k = (len(values_sorted) - 1) * (p / 100.0)
        f = int(k)
        c = min(f + 1, len(values_sorted) - 1)
        if f == c:
            return values_sorted[f]
        d0 = values_sorted[f] * (c - k)
        d1 = values_sorted[c] * (k - f)
        return d0 + d1

    notarize = key_values["notarize_latency_ms"]
    finalize = key_values["finalize_latency_ms"]
    bls_agg = key_values["bls_agg_ms"]
    p2p_bytes = key_values["p2p_vote_bytes"]
    gossip_bytes = key_values["gossip_vote_bytes"]
    cert_bytes = key_values["certificate_bytes"]

    total_paths = sum(path_counts.values())
    fast_ratio = float(path_counts["fast"]) / total_paths if total_paths else 0.0
    slow_ratio = float(path_counts["slow"]) / total_paths if total_paths else 0.0
    fail_ratio = float(path_counts["fail"]) / total_paths if total_paths else 0.0

    metrics: Dict[str, float] = {
        "votor_notarize_avg_ms": avg(notarize),
        "votor_notarize_p50_ms": percentile(notarize, 50),
        "votor_notarize_p95_ms": percentile(notarize, 95),
        "votor_notarize_p99_ms": percentile(notarize, 99),
        "votor_finalize_avg_ms": avg(finalize),
        "votor_finalize_p50_ms": percentile(finalize, 50),
        "votor_finalize_p95_ms": percentile(finalize, 95),
        "votor_finalize_p99_ms": percentile(finalize, 99),
        "votor_bls_agg_avg_ms": avg(bls_agg),
        "votor_bls_agg_p95_ms": percentile(bls_agg, 95),
        "votor_p2p_vote_bytes_avg": avg(p2p_bytes),
        "votor_gossip_vote_bytes_avg": avg(gossip_bytes),
        "votor_certificate_bytes_avg": avg(cert_bytes),
        "votor_path_fast_ratio": fast_ratio,
        "votor_path_slow_ratio": slow_ratio,
        "votor_path_fail_ratio": fail_ratio,
        "votor_path_fast_count": float(path_counts["fast"]),
        "votor_path_slow_count": float(path_counts["slow"]),
        "votor_path_fail_count": float(path_counts["fail"]),
    }
    if metrics["votor_gossip_vote_bytes_avg"] > 0:
        metrics["votor_p2p_over_gossip_bytes_ratio"] = (
            metrics["votor_p2p_vote_bytes_avg"] / metrics["votor_gossip_vote_bytes_avg"]
        )
    else:
        metrics["votor_p2p_over_gossip_bytes_ratio"] = 0.0
    return metrics


def parse_pow_metrics(log_dir: Path) -> Dict[str, float]:
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    key_values: Dict[str, List[float]] = {
        "block_interval_ms": [],
        "tx_latency_ms": [],
        "orphan_rate": [],
        "orphan_flag": [],
        "difficulty": [],
        "tx_per_block": [],
        "hash_attempts": [],
        "height": [],
    }
    for log_file in log_dir.glob("**/*.log"):
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean_line = ansi_pattern.sub("", line)
            if "pow_metrics" not in clean_line.lower():
                continue
            for part in clean_line.split():
                if "=" not in part:
                    continue
                key, value = part.split("=", 1)
                key = key.strip().lower()
                if key not in key_values:
                    continue
                try:
                    key_values[key].append(float(value.strip().lower()))
                except ValueError:
                    continue

    def avg(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    block_count = float(len(key_values["block_interval_ms"]))
    orphan_blocks = float(sum(key_values["orphan_flag"]))
    orphan_rate_observed = orphan_blocks / block_count if block_count > 0 else 0.0
    metrics: Dict[str, float] = {
        "pow_block_interval_avg_ms": avg(key_values["block_interval_ms"]),
        "pow_tx_latency_avg_ms": avg(key_values["tx_latency_ms"]),
        "pow_orphan_rate_avg": avg(key_values["orphan_rate"]),
        "pow_orphan_rate_observed": orphan_rate_observed,
        "pow_orphan_blocks": orphan_blocks,
        "pow_block_count": block_count,
        "pow_difficulty_avg": avg(key_values["difficulty"]),
        "pow_tx_per_block_avg": avg(key_values["tx_per_block"]),
        "pow_hash_attempts_avg": avg(key_values["hash_attempts"]),
        "pow_latest_height": max(key_values["height"]) if key_values["height"] else 0.0,
    }
    return metrics


def _parse_patterns(log_dir: Path, patterns: List[re.Pattern]) -> List[float]:
    values: List[float] = []
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    for log_file in log_dir.glob("**/*.log"):
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean_line = ansi_pattern.sub("", line)
            for pattern in patterns:
                match = pattern.search(clean_line)
                if match:
                    values.append(float(match.group(1)))
    return values


def _count_patterns(log_dir: Path, patterns: List[re.Pattern]) -> int:
    count = 0
    ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    for log_file in log_dir.glob("**/*.log"):
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            clean_line = ansi_pattern.sub("", line)
            for pattern in patterns:
                if pattern.search(clean_line):
                    count += 1
                    break
    return count


def _parse_rocksdb_stat(log_dir: Path, key: str) -> List[float]:
    data_dir = log_dir.parent.parent / "data" / log_dir.name
    if not data_dir.exists():
        return []
    pattern = re.compile(re.escape(key) + r".*?([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
    values: List[float] = []
    for log_file in _iter_log_files(data_dir):
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = pattern.search(line)
            if match:
                values.append(float(match.group(1)))
    return values


def _parse_rocksdb_log_files(data_dir: Path) -> List[float]:
    values: List[float] = []
    time_pattern = re.compile(r"T[·\.]\s*([\d.]+)\s*(ms|µs|us|s)", re.IGNORECASE)
    for log_file in data_dir.glob("**/*"):
        if not log_file.is_file():
            continue
        if log_file.name != "LOG" and not log_file.name.endswith(".log"):
            continue
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = time_pattern.search(line)
            if not match:
                continue
            value = float(match.group(1))
            unit = match.group(2).lower()
            if unit == "s":
                values.append(value * 1000.0)
            elif unit in {"us", "µs"}:
                values.append(value / 1000.0)
            else:
                values.append(value)
    return values


def _iter_log_files(data_dir: Path) -> List[Path]:
    files: List[Path] = []
    for log_file in data_dir.glob("**/*"):
        if not log_file.is_file():
            continue
        if log_file.name != "LOG" and not log_file.name.endswith(".log"):
            continue
        files.append(log_file)
    return files
