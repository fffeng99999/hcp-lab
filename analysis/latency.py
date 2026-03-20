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


def mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def variance(values: List[float]) -> float:
    if len(values) <= 1:
        return 0.0
    m = mean(values)
    return sum((v - m) * (v - m) for v in values) / (len(values) - 1)


def stddev(values: List[float]) -> float:
    return variance(values) ** 0.5


def jitter(values: List[float]) -> Dict[str, float]:
    if not values:
        return {
            "stddev_ms": 0.0,
            "p95_p50_ms": 0.0,
            "p99_p50_ms": 0.0,
            "iqr_ms": 0.0,
        }
    p25 = percentile(values, 25)
    p50 = percentile(values, 50)
    p75 = percentile(values, 75)
    p95 = percentile(values, 95)
    p99 = percentile(values, 99)
    return {
        "stddev_ms": stddev(values),
        "p95_p50_ms": p95 - p50,
        "p99_p50_ms": p99 - p50,
        "iqr_ms": p75 - p25,
    }
