import itertools
import json
from pathlib import Path
from typing import Dict, Iterable, List, Any


def build_matrix(params: Dict[str, Iterable[Any]]) -> List[Dict[str, Any]]:
    keys = list(params.keys())
    values = [list(params[key]) for key in keys]
    matrix = []
    for combo in itertools.product(*values):
        matrix.append({key: value for key, value in zip(keys, combo)})
    return matrix


def load_matrix(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return build_matrix(data)
    if isinstance(data, list):
        return data
    return []
