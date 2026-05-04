import json
import os
import signal
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional


class NodeManager:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.hcp_dir = project_root / "hcp"
        self.process: Optional[subprocess.Popen] = None

    def start_nodes(
        self,
        num_nodes: int,
        data_root: Path,
        log_dir: Path,
        use_cpu_affinity: bool = True,
        storage_group_size: Optional[int] = None,
        timeout: int = 300,
        extra_account_count: Optional[int] = None,
    ) -> subprocess.Popen:
        env = os.environ.copy()
        env["DATA_ROOT"] = str(data_root)
        env["LOG_DIR"] = str(log_dir)
        if use_cpu_affinity:
            env["USE_CPU_AFFINITY"] = "true"
        if storage_group_size is not None:
            env["STORAGE_GROUP_SIZE"] = str(storage_group_size)
        if extra_account_count is not None:
            env["EXTRA_ACCOUNT_COUNT"] = str(extra_account_count)
        cmd = ["bash", "start_nodes.sh", str(num_nodes)]
        self.process = subprocess.Popen(
            cmd,
            cwd=str(self.hcp_dir),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        port_offset = int(env.get("PORT_OFFSET", "0"))
        if not wait_for_rpc(26657 + port_offset, timeout=timeout):
            self.stop_nodes()
            raise RuntimeError("节点启动超时")
        return self.process

    def stop_nodes(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        binary = os.environ.get("HCPD_BINARY")
        pattern = f"{binary} start" if binary else "hcpd start"
        subprocess.run(
            ["pkill", "-f", pattern],
            cwd=str(self.hcp_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def wait_for_rpc(port: int, timeout: int = 60) -> bool:
    url = f"http://127.0.0.1:{port}/status"
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status != 200:
                    continue
                payload = resp.read()
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    time.sleep(1)
                    continue
                height_raw = (
                    data.get("result", {})
                    .get("sync_info", {})
                    .get("latest_block_height", "0")
                )
                try:
                    height = int(height_raw)
                except (TypeError, ValueError):
                    height = 0
                if height > 0:
                    return True
        except Exception:
            time.sleep(1)
    return False
