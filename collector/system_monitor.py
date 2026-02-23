import threading
import time
from typing import Tuple


class SystemMonitor:
    def __init__(self, interval: float = 1.0) -> None:
        self.interval = interval
        self._running = False
        self._cpu_samples = []
        self._mem_samples = []
        self._thread: threading.Thread | None = None
        self._net_start = 0.0
        self._loop_start = 0.0

    def start(self) -> None:
        self._running = True
        self._cpu_samples = []
        self._mem_samples = []
        self._last_cpu = read_cpu_times()
        self._loop_start = time.time()
        self._net_start = read_net_bytes()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> Tuple[float, float, float]:
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval * 2)
        cpu = self._cpu_samples[-1] if self._cpu_samples else 0.0
        mem = self._mem_samples[-1] if self._mem_samples else 0.0
        elapsed = max(time.time() - self._loop_start, self.interval) if self._loop_start else self.interval
        try:
            net_now = read_net_bytes()
            net_bytes = max(net_now - self._net_start, 0.0)
        except Exception:
            net_bytes = 0.0
        net_mbps = net_bytes * 8.0 / (elapsed * 1024.0 * 1024.0) if elapsed > 0 else 0.0
        return cpu, mem, net_mbps

    def sample(self) -> None:
        if not self._running:
            return
        current = read_cpu_times()
        cpu_percent = calc_cpu_percent(self._last_cpu, current)
        mem_bytes = read_mem_bytes()
        self._last_cpu = current
        self._cpu_samples.append(cpu_percent)
        self._mem_samples.append(mem_bytes)

    def _run(self) -> None:
        while self._running:
            self.sample()
            time.sleep(self.interval)


def read_cpu_times() -> Tuple[int, int]:
    with open("/proc/stat", "r", encoding="utf-8") as f:
        parts = f.readline().split()
    values = list(map(int, parts[1:]))
    idle = values[3] + values[4]
    total = sum(values)
    return idle, total


def calc_cpu_percent(prev: Tuple[int, int], current: Tuple[int, int]) -> float:
    prev_idle, prev_total = prev
    curr_idle, curr_total = current
    total_delta = curr_total - prev_total
    idle_delta = curr_idle - prev_idle
    if total_delta <= 0:
        return 0.0
    return (1.0 - idle_delta / total_delta) * 100.0


def read_mem_bytes() -> float:
    with open("/proc/meminfo", "r", encoding="utf-8") as f:
        data = f.read().splitlines()
    mem_total = 0.0
    mem_available = 0.0
    for line in data:
        if line.startswith("MemTotal:"):
            mem_total = float(line.split()[1]) * 1024.0
        elif line.startswith("MemAvailable:"):
            mem_available = float(line.split()[1]) * 1024.0
    return max(mem_total - mem_available, 0.0)


def read_net_bytes() -> float:
    total = 0.0
    with open("/proc/net/dev", "r", encoding="utf-8") as f:
        lines = f.read().splitlines()[2:]
    for line in lines:
        if ":" not in line:
            continue
        iface, data = line.split(":", 1)
        iface = iface.strip()
        if iface == "lo":
            continue
        parts = data.split()
        if len(parts) >= 16:
            rx = float(parts[0])
            tx = float(parts[8])
            total += rx + tx
    return total
