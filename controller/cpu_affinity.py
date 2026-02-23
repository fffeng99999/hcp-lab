import os
from typing import Iterable, List


def available_cores() -> List[int]:
    return list(range(os.cpu_count() or 1))


def set_affinity(pid: int, cores: Iterable[int]) -> None:
    os.sched_setaffinity(pid, set(cores))


def assign_round_robin(pids: Iterable[int], cores: Iterable[int]) -> None:
    core_list = list(cores) or available_cores()
    for index, pid in enumerate(pids):
        core = core_list[index % len(core_list)]
        set_affinity(pid, [core])
