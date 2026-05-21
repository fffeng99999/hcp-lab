#!/usr/bin/env python3
"""Run official CometBFT/Cosmos SDK nodes for paper table 3-3."""
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from statistics import stdev
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_engine_runner import (
    DEFAULT_DATABASE_URL,
    aggregate_runs as aggregate_engine_runs,
    ensure_dirs,
    env_int,
    env_list_int,
    prepare_sdk_account_file,
    run_engine_loadgen_point,
    save_json,
    save_md,
    stage_binaries,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
REPORT_DIR = SCRIPT_DIR / "report"
TEST_DIR = PROJECT_ROOT / "tests" / "exp0_cometbft_compare"


def avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def sd(values: list[float]) -> float:
    return stdev(values) if len(values) > 1 else 0.0


def fmt(mean: float, std: float) -> str:
    return f"{mean:.2f}±{std:.2f}"


def run(cmd: list[str], cwd: Path | None = None, input_text: str | None = None) -> subprocess.CompletedProcess:
    res = subprocess.run(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"command failed rc={res.returncode}: {' '.join(cmd)}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        )
    return res


def read_json(output: str) -> dict[str, Any]:
    text = output.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"no json object in output: {output[:300]}")
    return json.loads(text[start : end + 1])


def find_port_window(nodes: int) -> int:
    for _ in range(200):
        base = random.randint(20000, 43000)
        ports = []
        for i in range(nodes):
            ports.extend([base + i * 10, base + i * 10 + 1, base + 1000 + i])
        ok = True
        for port in ports:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    ok = False
                    break
        if ok:
            return base
    raise RuntimeError("could not find a free port window")


def replace_config(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    path.write_text(text, encoding="utf-8")


def wait_rpc(rpc_port: int, timeout_s: float = 45) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    url = f"http://127.0.0.1:{rpc_port}/status"
    last_err = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            height = int(data["result"]["sync_info"]["latest_block_height"])
            if height >= 1:
                return data
        except Exception as err:  # noqa: BLE001
            last_err = err
        time.sleep(1)
    raise TimeoutError(f"timeout waiting for rpc {url}: {last_err}")


def rpc_json(rpc_port: int, path: str) -> dict[str, Any]:
    with urllib.request.urlopen(f"http://127.0.0.1:{rpc_port}{path}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest_height(rpc_port: int) -> int:
    data = rpc_json(rpc_port, "/status")
    return int(data["result"]["sync_info"]["latest_block_height"])


def count_block_txs(rpc_port: int, from_height: int, to_height: int) -> int:
    total = 0
    for height in range(max(1, from_height), to_height + 1):
        try:
            data = rpc_json(rpc_port, f"/block?height={height}")
            txs = data["result"]["block"]["data"].get("txs") or []
            total += len(txs)
        except Exception:
            continue
    return total


def configure_node(home: Path, rpc_port: int, p2p_port: int, grpc_port: int, peers: str) -> None:
    replace_config(
        home / "config" / "config.toml",
        [
            (r'laddr = "tcp://127\.0\.0\.1:26657"', f'laddr = "tcp://127.0.0.1:{rpc_port}"'),
            (r'laddr = "tcp://0\.0\.0\.0:26656"', f'laddr = "tcp://0.0.0.0:{p2p_port}"'),
            (r'pprof_laddr = ".*"', f'pprof_laddr = "localhost:{grpc_port + 1000}"'),
            (r'allow_duplicate_ip = false', "allow_duplicate_ip = true"),
            (r'addr_book_strict = true', "addr_book_strict = false"),
            (r'persistent_peers = ".*"', f'persistent_peers = "{peers}"'),
            (r'timeout_propose = ".*"', f'timeout_propose = "{os.environ.get("COMET_TIMEOUT_PROPOSE", "500ms")}"'),
            (r'timeout_prevote = ".*"', f'timeout_prevote = "{os.environ.get("COMET_TIMEOUT_PREVOTE", "200ms")}"'),
            (r'timeout_precommit = ".*"', f'timeout_precommit = "{os.environ.get("COMET_TIMEOUT_PRECOMMIT", "200ms")}"'),
            (r'timeout_commit = ".*"', f'timeout_commit = "{os.environ.get("COMET_TIMEOUT_COMMIT", "1s")}"'),
            (r'skip_timeout_commit = .*', f'skip_timeout_commit = {os.environ.get("COMET_SKIP_TIMEOUT_COMMIT", "true").lower()}'),
            (r'recheck = .*', f'recheck = {os.environ.get("COMET_MEMPOOL_RECHECK", "false").lower()}'),
        ],
    )
    replace_config(
        home / "config" / "app.toml",
        [
            (r'address = "localhost:9090"', f'address = "127.0.0.1:{grpc_port}"'),
            (r'address = "0\.0\.0\.0:9090"', f'address = "127.0.0.1:{grpc_port}"'),
        ],
    )


def prepare_network(point_dir: Path, hcpd: Path, nodes: int, txs: int, chain_id: str) -> tuple[Path, int, int, Path]:
    if point_dir.exists():
        shutil.rmtree(point_dir)
    point_dir.mkdir(parents=True, exist_ok=True)
    account_file = point_dir / "loadgen_accounts.jsonl"
    homes = [point_dir / f"node{i}" for i in range(nodes)]

    for i, home in enumerate(homes):
        run([str(hcpd), "init", f"node{i}", "--chain-id", chain_id, "--home", str(home)])
        key = read_json(run([str(hcpd), "keys", "add", f"validator{i}", "--keyring-backend", "test", "--home", str(home), "--output", "json"]).stdout)
        run([str(hcpd), "genesis", "add-genesis-account", key["address"], "100000000000stake", "--home", str(home)])
        run([str(hcpd), "genesis", "gentx", f"validator{i}", "1000000stake", "--chain-id", chain_id, "--keyring-backend", "test", "--home", str(home)])

    for i, home in enumerate(homes[1:], start=1):
        addr = run([str(hcpd), "keys", "show", f"validator{i}", "-a", "--keyring-backend", "test", "--home", str(home)]).stdout.strip()
        run([str(hcpd), "genesis", "add-genesis-account", addr, "100000000000stake", "--home", str(homes[0])])
        gentx_dir = homes[0] / "config" / "gentx"
        gentx_dir.mkdir(parents=True, exist_ok=True)
        for gentx in (home / "config" / "gentx").glob("*.json"):
            shutil.copy2(gentx, gentx_dir / gentx.name)

    if bool_env("COMET_SIGNED_TXS", True):
        with account_file.open("w", encoding="utf-8") as out:
            for i in range(txs):
                name = f"load{i:04d}"
                key = read_json(run([str(hcpd), "keys", "add", name, "--keyring-backend", "test", "--home", str(homes[0]), "--output", "json"]).stdout)
                out.write(json.dumps({"name": name, "address": key["address"]}) + "\n")
                run([str(hcpd), "genesis", "add-genesis-account", key["address"], "100000000000stake", "--home", str(homes[0])])
    else:
        account_file = prepare_sdk_account_file(point_dir, point_dir.name, txs)
        for line in account_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            address = json.loads(line)["address"]
            run([str(hcpd), "genesis", "add-genesis-account", address, "100000000000stake", "--home", str(homes[0])])

    run([str(hcpd), "genesis", "collect-gentxs", "--home", str(homes[0])])
    for home in homes[1:]:
        shutil.copy2(homes[0] / "config" / "genesis.json", home / "config" / "genesis.json")

    base_port = find_port_window(nodes)
    peer_parts = []
    for i, home in enumerate(homes):
        node_id = run([str(hcpd), "comet", "show-node-id", "--home", str(home)]).stdout.strip()
        peer_parts.append(f"{node_id}@127.0.0.1:{base_port + i * 10 + 1}")
    peers = ",".join(peer_parts)
    for i, home in enumerate(homes):
        configure_node(home, base_port + i * 10, base_port + i * 10 + 1, base_port + 1000 + i, peers)
    return homes[0], base_port, base_port + 1000, account_file


def parse_last_snapshot(stdout: str) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "actual_tps" in obj or "sent" in obj:
            last = obj
    return last


def loadgen_database_url() -> str:
    url = os.environ.get("LOADGEN_DATABASE_URL", DEFAULT_DATABASE_URL)
    return re.sub(r"([?&])search_path=[^&]+&?", r"\1", url).rstrip("?&")


def bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def run_point(hcpd: Path, loadgen: Path, nodes: int, txs: int, repeat: int) -> dict[str, Any]:
    point = f"cometbft_n{nodes}_uniform_t{txs}_r{repeat}"
    point_dir = TEST_DIR / "data" / point
    log_dir = TEST_DIR / "logs"
    csv_dir = TEST_DIR / "csv"
    log_dir.mkdir(parents=True, exist_ok=True)
    csv_dir.mkdir(parents=True, exist_ok=True)
    chain_id = f"{point}-chain"
    node0_home, rpc_port, grpc_port, account_file = prepare_network(point_dir, hcpd, nodes, txs, chain_id)

    procs: list[subprocess.Popen] = []
    try:
        for i in range(nodes):
            home = point_dir / f"node{i}"
            log_file = (log_dir / f"{point}_node{i}.log").open("w", encoding="utf-8", errors="replace")
            proc = subprocess.Popen(
                [
                    str(hcpd),
                    "start",
                    "--home",
                    str(home),
                    "--minimum-gas-prices",
                    "0stake",
                    "--consensus-engine",
                    "noop",
                    "--grpc.enable=true",
                    "--grpc.address",
                    f"127.0.0.1:{grpc_port + i}",
                    "--api.enable=false",
                    "--grpc-web.enable=false",
                ],
                cwd=point_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            procs.append(proc)
        wait_rpc(rpc_port)
        start_height = latest_height(rpc_port)
        schema = f"lg_exp0_cometbft_compare_{point}"
        loadgen_cmd = [
            str(loadgen),
            "--protocol",
            "grpc",
            "--grpc-endpoint",
            f"http://127.0.0.1:{grpc_port}",
            "--chain-id",
            chain_id,
            "--broadcast-mode",
            os.environ.get("COMET_BROADCAST_MODE", "sync"),
            "--mode",
            "sustained",
            "--total-txs",
            str(txs),
            "--concurrency",
            os.environ.get("COMET_LOADGEN_CONCURRENCY", "16"),
            "--worker-threads",
            os.environ.get("COMET_LOADGEN_WORKERS", "4"),
            "--account-count",
            str(txs),
            "--account-file",
            str(account_file),
            "--account-selection-mode",
            "round_robin",
            "--initial-balance",
            "100000000000",
            "--send-amount",
            "1",
            "--denom",
            "stake",
            "--fee-amount",
            "1",
            "--gas-limit",
            "200000",
            "--database-url",
            loadgen_database_url(),
            "--db-schema",
            schema,
            "--reset-schema-on-start",
            "true",
            "--csv-path",
            str(csv_dir / f"{point}_loadgen.csv"),
            "--prometheus-addr",
            "127.0.0.1:0",
            "--json-interval-ms",
            "1000",
        ]
        if bool_env("COMET_SIGNED_TXS", True):
            loadgen_cmd.extend(
                [
                    "--rpc-endpoint",
                    f"tcp://127.0.0.1:{rpc_port}",
                    "--keyring-backend",
                    "test",
                    "--keyring-home",
                    str(node0_home),
                    "--cli-binary",
                    str(hcpd),
                ]
            )
        started = time.time()
        completed = subprocess.run(
            loadgen_cmd,
            cwd=PROJECT_ROOT / "hcp-loadgen",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=env_int("COMET_LOADGEN_TIMEOUT", 600),
        )
        duration = time.time() - started
        (log_dir / f"{point}_loadgen.log").write_text(
            (completed.stdout or "") + "\n--- STDERR ---\n" + (completed.stderr or ""),
            encoding="utf-8",
        )
        time.sleep(float(os.environ.get("COMET_DRAIN_SECONDS", "3")))
        end_height = latest_height(rpc_port)
        committed_blocks_txs = count_block_txs(rpc_port, start_height, end_height)
        snap = parse_last_snapshot(completed.stdout)
        success = int(snap.get("success", 0))
        effective_success = max(success, committed_blocks_txs)
        metrics = {
            "tps": float(effective_success) / duration if duration > 0 else 0.0,
            "p50_ms": float(snap.get("latency_p50_ms", 0.0)),
            "p95_ms": float(snap.get("latency_p95_ms", snap.get("latency_p90_ms", 0.0))),
            "p99_ms": float(snap.get("latency_p99_ms", 0.0)),
            "success_rate": float(effective_success) / float(txs) if txs else 0.0,
            "committed_txs": committed_blocks_txs,
            "loadgen_success": success,
            "duration_s": duration,
            "start_height": start_height,
            "end_height": end_height,
            "loadgen_exit_code": completed.returncode,
        }
        result = {
            "params": {"point": point, "engine": "cometbft", "nodes": nodes, "txs": txs, "repeat": repeat, "db_schema": schema},
            "metrics": metrics,
            "loadgen": snap,
            "intermediate_paths": {"data_dir": str(point_dir), "account_file": str(account_file)},
        }
        save_json(result, REPORT_DIR / f"{point}.json")
        return result
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()


def aggregate(results: list[dict[str, Any]]) -> dict[str, float]:
    def vals(key: str) -> list[float]:
        return [float(r["metrics"].get(key, 0.0)) for r in results]

    return {
        "tps_mean": avg(vals("tps")),
        "tps_std": sd(vals("tps")),
        "p50_mean": avg(vals("p50_ms")),
        "p50_std": sd(vals("p50_ms")),
        "p95_mean": avg(vals("p95_ms")),
        "p95_std": sd(vals("p95_ms")),
        "p99_mean": avg(vals("p99_ms")),
        "p99_std": sd(vals("p99_ms")),
        "success_rate_mean": avg(vals("success_rate")),
        "success_rate_std": sd(vals("success_rate")),
    }


def load_existing_result(point: str) -> dict[str, Any] | None:
    if os.environ.get("EXP0_FORCE_RERUN", "").strip().lower() in {"1", "true", "yes"}:
        return None
    path = REPORT_DIR / f"{point}.json"
    if not path.exists():
        return None
    result = json.loads(path.read_text(encoding="utf-8"))
    if int(result.get("loadgen_exit_code", 0)) != 0:
        return None
    if float(result.get("metrics", {}).get("success_rate", 0.0)) < 0.999:
        return None
    return result


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    hcpd = Path(os.environ.get("HCPD_BIN", PROJECT_ROOT / "tests" / "build" / "hcpd.exe"))
    loadgen = Path(os.environ.get("HCP_LOADGEN_BIN", PROJECT_ROOT / "tests" / "build" / "hcp-loadgen.exe"))
    nodes_list = env_list_int("COMETBFT_ORIGINAL_NODES", [8, 16, 32])
    txs = env_int("COMETBFT_ORIGINAL_TXS", 1000)
    repeat = env_int("COMETBFT_ORIGINAL_REPEAT", 5)
    target_tps = env_int("COMETBFT_LIGHT_TARGET_TPS", 10000)
    paths = ensure_dirs("exp0_cometbft_compare", REPORT_DIR)
    binaries = stage_binaries(paths)

    matrix: dict[str, dict[str, Any]] = {"cometbft": {}, "cometbft-light": {}}
    for nodes in nodes_list:
        runs = []
        for r in range(1, repeat + 1):
            point = f"cometbft_n{nodes}_uniform_t{txs}_r{r}"
            existing = load_existing_result(point)
            if existing is not None:
                print(f"[COMETBFT] reuse {point}", flush=True)
                runs.append(existing)
                continue
            print(f"[COMETBFT] nodes={nodes} txs={txs} run={r}", flush=True)
            runs.append(run_point(hcpd, loadgen, nodes, txs, r))
        matrix["cometbft"][str(nodes)] = aggregate(runs)

        light_runs = []
        for r in range(1, repeat + 1):
            point = f"cometbft_light_n{nodes}_uniform_t{txs}_r{r}"
            existing = load_existing_result(point)
            if existing is not None:
                print(f"[COMETBFT-light] reuse {point}", flush=True)
                light_runs.append(existing)
                continue
            print(f"[COMETBFT-light] nodes={nodes} txs={txs} run={r}", flush=True)
            light_runs.append(
                run_engine_loadgen_point(
                    "exp0_cometbft_compare",
                    REPORT_DIR,
                    point,
                    "cometbft-light",
                    nodes,
                    txs,
                    target_tps,
                    binaries=binaries,
                    paths=paths,
                )
            )
        matrix["cometbft-light"][str(nodes)] = aggregate_engine_runs(light_runs)

    save_json(matrix, REPORT_DIR / "summary.json")
    md = [
        "## 表3-4 CometBFT 与 CometBFT-light 对比",
        "",
        f"统一负载：Uniform，tx={txs}，约250 bytes/tx。CometBFT 为官方 CometBFT/Cosmos SDK 多进程节点；CometBFT-light 为 HCP engine 轻量实现。",
        "",
        "| 算法 | 节点数N | TPS(tx/s) | P50(ms) | P95(ms) | P99(ms) | 成功率 |",
        "|------|---------|-----------|---------|---------|---------|--------|",
    ]
    for nodes in nodes_list:
        d = matrix["cometbft"][str(nodes)]
        md.append(
            f"| CometBFT | {nodes} | {fmt(d['tps_mean'], d['tps_std'])} | {fmt(d['p50_mean'], d['p50_std'])} | "
            f"{fmt(d['p95_mean'], d['p95_std'])} | {fmt(d['p99_mean'], d['p99_std'])} | {d['success_rate_mean']:.3f} |"
        )
        light = matrix["cometbft-light"].get(str(nodes))
        if light:
            md.append(
                f"| CometBFT-light | {nodes} | {fmt(light.get('tps_mean', 0), light.get('tps_std', 0))} | "
                f"{fmt(light.get('p50_mean', 0), light.get('p50_std', 0))} | "
                f"{fmt(light.get('p95_mean', 0), light.get('p95_std', 0))} | "
                f"{fmt(light.get('p99_mean', 0), light.get('p99_std', 0))} | {light.get('success_rate_mean', 0):.3f} |"
            )
    save_md(md, REPORT_DIR / "table3_4.md")
    print(f"[COMETBFT] done: {REPORT_DIR / 'table3_4.md'}", flush=True)


if __name__ == "__main__":
    main()
