def write_amplification(
    block_size: int,
    memtable_size: int,
    level_ratio: int = 10,
    levels: int = 4,
) -> float:
    if block_size <= 0 or memtable_size <= 0:
        return 0.0
    base = memtable_size / block_size
    amplification = 1.0
    for level in range(levels):
        amplification += base * (level_ratio ** level)
    return amplification
