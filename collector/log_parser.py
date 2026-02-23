import re
from pathlib import Path
from typing import List


BLOCK_PATTERNS = [
    re.compile(r"block[_\s]?time[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
    re.compile(r"block\s+latency[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
]

CONFIRM_PATTERNS = [
    re.compile(r"confirm[_\s]?time[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
    re.compile(r"tx\s+confirm[:=]\s*([\d.]+)\s*ms", re.IGNORECASE),
]

ROCKSDB_PATTERNS = [
    re.compile(r"rocksdb_write.*duration_ms[=:]\s*([\d.]+)", re.IGNORECASE),
]


def parse_block_times(log_dir: Path) -> List[float]:
    return _parse_patterns(log_dir, BLOCK_PATTERNS)


def parse_confirm_times(log_dir: Path) -> List[float]:
    return _parse_patterns(log_dir, CONFIRM_PATTERNS)


def parse_rocksdb_times(log_dir: Path) -> List[float]:
    return _parse_patterns(log_dir, ROCKSDB_PATTERNS)


def _parse_patterns(log_dir: Path, patterns: List[re.Pattern]) -> List[float]:
    values: List[float] = []
    for log_file in log_dir.glob("**/*.log"):
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    values.append(float(match.group(1)))
    return values
