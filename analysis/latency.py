from typing import Dict, Iterable, List


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


def percentiles(values: List[float], ps: Iterable[float]) -> Dict[float, float]:
    return {p: percentile(values, p) for p in ps}


def histogram(values: List[float], bins: int = 10) -> Dict[str, int]:
    if not values or bins <= 0:
        return {}
    min_v = min(values)
    max_v = max(values)
    if min_v == max_v:
        return {f"{min_v:.2f}": len(values)}
    step = (max_v - min_v) / bins
    counts = {f"{min_v + i * step:.2f}": 0 for i in range(bins)}
    for v in values:
        idx = min(int((v - min_v) / step), bins - 1)
        key = f"{min_v + idx * step:.2f}"
        counts[key] += 1
    return counts
