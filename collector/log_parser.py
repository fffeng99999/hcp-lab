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
