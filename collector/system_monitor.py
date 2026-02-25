import os
import shutil
import subprocess
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
        self._iostat = IOStatMonitor(interval)

    def start(self) -> None:
        self._running = True
        self._cpu_samples = []
        self._mem_samples = []
        self._last_cpu = read_cpu_times()
        self._loop_start = time.time()
        self._net_start = read_net_bytes()
        self._iostat.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> Tuple[float, float, float, float, float, float, float]:
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
        io_util, io_await, io_read_s, io_write_s = self._iostat.stop()
        return cpu, mem, net_mbps, io_util, io_await, io_read_s, io_write_s

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
    include_loopback = os.environ.get("INCLUDE_LOOPBACK", "").lower() in ("1", "true", "yes")
    with open("/proc/net/dev", "r", encoding="utf-8") as f:
        lines = f.read().splitlines()[2:]
    for line in lines:
        if ":" not in line:
            continue
        iface, data = line.split(":", 1)
        iface = iface.strip()
        if iface == "lo" and not include_loopback:
            continue
        parts = data.split()
        if len(parts) >= 16:
            rx = float(parts[0])
            tx = float(parts[8])
            total += rx + tx
    return total


class IOStatMonitor:
    def __init__(self, interval: float) -> None:
        self.interval = interval
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._samples: list[Tuple[float, float, float, float]] = []
        self._current: list[Tuple[float, float, float, float]] = []
        self._header: list[str] = []
        self._col_map: dict[str, int] = {}

    def start(self) -> None:
        if not shutil.which("iostat"):
            return
        self._running = True
        self._samples = []
        self._current = []
        self._header = []
        self._col_map = {}
        self._process = subprocess.Popen(
            ["iostat", "-x", str(self.interval)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def stop(self) -> Tuple[float, float, float, float]:
        self._running = False
        if self._process:
            self._process.terminate()
        if self._thread:
            self._thread.join(timeout=self.interval * 2)
        self._finalize_current()
        if not self._samples:
            return 0.0, 0.0, 0.0, 0.0
        util = sum(sample[0] for sample in self._samples) / len(self._samples)
        await_ms = sum(sample[1] for sample in self._samples) / len(self._samples)
        read_s = sum(sample[2] for sample in self._samples) / len(self._samples)
        write_s = sum(sample[3] for sample in self._samples) / len(self._samples)
        return util, await_ms, read_s, write_s

    def _read(self) -> None:
        if not self._process or self._process.stdout is None:
            return
        for raw in self._process.stdout:
            if not self._running:
                break
            line = raw.strip()
            if not line:
                continue
            if line.startswith("Device"):
                self._finalize_current()
                self._header = line.split()
                self._col_map = {name: index for index, name in enumerate(self._header)}
                continue
            if not self._header:
                continue
            if line.startswith("avg-cpu") or line.startswith("Linux"):
                continue
            parts = line.split()
            if len(parts) < len(self._header):
                continue
            name = parts[0]
            if name.startswith("loop") or name.startswith("ram") or name.startswith("sr"):
                continue
            util = self._read_col(parts, "%util")
            await_ms = self._read_col(parts, "await")
            read_s = self._read_col(parts, "r/s")
            write_s = self._read_col(parts, "w/s")
            if util is None:
                continue
            self._current.append(
                (
                    util,
                    await_ms or 0.0,
                    read_s or 0.0,
                    write_s or 0.0,
                )
            )

    def _read_col(self, parts: list[str], name: str) -> float | None:
        index = self._col_map.get(name)
        if index is None or index >= len(parts):
            return None
        try:
            return float(parts[index])
        except ValueError:
            return None

    def _finalize_current(self) -> None:
        if not self._current:
            return
        best = max(self._current, key=lambda item: item[0])
        self._samples.append(best)
        self._current = []
