from typing import List


def compute_tps(tx_count: int, duration_s: float) -> float:
    if duration_s <= 0:
        return 0.0
    return tx_count / duration_s


def compute_from_blocks(block_times_ms: List[float], tx_per_block: int) -> float:
    if not block_times_ms:
        return 0.0
    avg_block_s = sum(block_times_ms) / len(block_times_ms) / 1000.0
    if avg_block_s <= 0:
        return 0.0
    return tx_per_block / avg_block_s


def rolling_tps(timestamps: List[float], window_s: float) -> List[float]:
    if not timestamps or window_s <= 0:
        return []
    result = []
    start = 0
    for i, ts in enumerate(timestamps):
        while ts - timestamps[start] > window_s:
            start += 1
        count = i - start + 1
        result.append(count / window_s)
    return result
