import math
from typing import List


def binomial_pmf(n: int, k: int, p: float) -> float:
    if k < 0 or k > n:
        return 0.0
    return math.comb(n, k) * (p**k) * ((1 - p) ** (n - k))


def failure_probability(node_count: int, byzantine_ratio: float, threshold_ratio: float = 1 / 3) -> float:
    threshold = math.floor(node_count * threshold_ratio) + 1
    prob = 0.0
    for k in range(threshold, node_count + 1):
        prob += binomial_pmf(node_count, k, byzantine_ratio)
    return prob


def failure_curve(node_counts: List[int], byzantine_ratio: float, threshold_ratio: float = 1 / 3) -> List[float]:
    return [failure_probability(n, byzantine_ratio, threshold_ratio) for n in node_counts]
