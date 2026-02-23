from pathlib import Path
from typing import Dict, List


def parse_prometheus_text(text: str) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            name = parts[0]
            try:
                metrics[name] = float(parts[-1])
            except ValueError:
                continue
    return metrics


def parse_prometheus_file(path: Path) -> Dict[str, float]:
    return parse_prometheus_text(path.read_text(encoding="utf-8", errors="ignore"))


def read_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not path.exists():
        return rows
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if not lines:
        return rows
    headers = lines[0].split(",")
    for line in lines[1:]:
        values = line.split(",")
        rows.append({key: value for key, value in zip(headers, values)})
    return rows
