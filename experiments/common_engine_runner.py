#!/usr/bin/env python3
"""Shared runner for HCP engine + loadgen experiments.

Final experiment data is written to hcp-lab/experiments/<exp>/report.
Intermediate artifacts are written to project-root tests/<exp>.
"""
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from hashlib import sha256
from pathlib import Path
from statistics import stdev as _stdev
from typing import Any, Dict, Iterable, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"
DEFAULT_DATABASE_URL = (
    "postgres://user_rbc3B8:password_DfA4Pw@192.168.58.102:5432/"
    "hcp_server?sslmode=disable&search_path=loadgendata,public"
)

BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def avg(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0


def stdev(values: Iterable[float]) -> float:
    vals = list(values)
    return _stdev(vals) if len(vals) > 1 else 0.0


def sem(values: Iterable[float]) -> float:
    vals = list(values)
    return stdev(vals) / (len(vals) ** 0.5) if len(vals) > 1 else 0.0


def ci95(values: Iterable[float]) -> List[float]:
    vals = list(values)
    if len(vals) <= 1:
        return [0.0, 0.0]
    t = 2.776 if len(vals) == 5 else (2.262 if len(vals) == 10 else 2.0)
    m = avg(vals)
    margin = t * sem(vals)
    return [m - margin, m + margin]


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def env_list_int(name: str, default: List[int]) -> List[int]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return [int(v.strip()) for v in raw.split(",") if v.strip()]


def env_list_str(name: str, default: List[str]) -> List[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return [v.strip() for v in raw.split(",") if v.strip()]


def ensure_dirs(exp_name: str, report_dir: Path) -> Dict[str, Path]:
    root = TESTS_DIR / exp_name
    paths = {
        "root": root,
        "bin": root / "bin",
        "data": root / "data",
        "logs": root / "logs",
        "csv": root / "csv",
        "report": report_dir,
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def clean_report(report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    for item in report_dir.iterdir():
        if item.is_file():
            item.unlink()


def resolve_binary(env_name: str, candidates: List[Path]) -> Path:
    override = os.environ.get(env_name, "").strip()
    if override:
        path = Path(override)
        if path.exists():
            return path
        raise FileNotFoundError(f"{env_name}={override} does not exist")
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"Cannot find binary for {env_name}")


def stage_binary(src: Path, dst_dir: Path, name: str) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{name}{src.suffix}"
    try:
        shutil.copy2(src, dst)
    except PermissionError:
        if dst.exists():
            print(f"[WARN] reuse locked staged binary {dst}", flush=True)
            return dst
        raise
    return dst


def stage_binaries(paths: Dict[str, Path]) -> Dict[str, Path]:
    bench = resolve_binary(
        "HCP_BENCH_BIN",
        [
            PROJECT_ROOT / "tests" / "build" / "hcp-bench.exe",
            PROJECT_ROOT / "tests" / "build" / "hcp-bench",
            PROJECT_ROOT / "hcp-consensus" / "hcp-bench.exe",
            PROJECT_ROOT / "hcp-consensus" / "hcp-bench",
            PROJECT_ROOT / "hcp-consensus-build" / "hcp-bench.exe",
            PROJECT_ROOT / "hcp-consensus-build" / "hcp-bench",
        ],
    )
    loadgen = resolve_binary(
        "HCP_LOADGEN_BIN",
        [
            PROJECT_ROOT / "tests" / "build" / "hcp-loadgen.exe",
            PROJECT_ROOT / "tests" / "build" / "hcp-loadgen",
            PROJECT_ROOT / "hcp-loadgen" / "target" / "release" / "hcp-loadgen.exe",
            PROJECT_ROOT / "hcp-loadgen" / "target" / "release" / "hcp-loadgen",
            PROJECT_ROOT / "hcp-loadgen" / "target" / "debug" / "hcp-loadgen.exe",
            PROJECT_ROOT / "hcp-loadgen" / "target" / "debug" / "hcp-loadgen",
        ],
    )
    return {
        "bench": stage_binary(bench, paths["bin"], "hcp-bench"),
        "loadgen": stage_binary(loadgen, paths["bin"], "hcp-loadgen"),
    }


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_http(url: str, timeout_s: int = 30) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.5)
    raise TimeoutError(f"Timeout waiting for {url}")


def get_json(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_engine_complete(endpoint: str, expected_txs: int, timeout_s: float) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    last: Dict[str, Any] = {}
    url = f"{endpoint}/status?expected={expected_txs}"
    stable_since: Optional[float] = None
    last_committed = -1
    stable_seconds = float(os.environ.get("ENGINE_STABLE_SECONDS", "2"))
    while time.time() < deadline:
        last = get_json(url)
        committed = int(last.get("committed_txs", 0))
        accepted = int(last.get("accepted_txs", 0))
        if committed >= expected_txs:
            return last
        if committed != last_committed:
            last_committed = committed
            stable_since = time.time()
        elif accepted >= expected_txs and committed > 0 and stable_since is not None:
            if time.time() - stable_since >= stable_seconds:
                return last
        time.sleep(0.1)
    return last or get_json(url)


def parse_last_json_line(text: str) -> Dict[str, Any]:
    last: Dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "actual_tps" in value or "sent" in value:
            last = value
    return last


def sanitize(value: str) -> str:
    out = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    if not out:
        out = "point"
    if out[0].isdigit():
        out = f"p_{out}"
    return out[:63]


def bech32_polymod(values: List[int]) -> int:
    generators = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for i, generator in enumerate(generators):
            if (top >> i) & 1:
                chk ^= generator
    return chk


def bech32_hrp_expand(hrp: str) -> List[int]:
    return [ord(ch) >> 5 for ch in hrp] + [0] + [ord(ch) & 31 for ch in hrp]


def convertbits(data: bytes, from_bits: int, to_bits: int, pad: bool = True) -> List[int]:
    acc = 0
    bits = 0
    ret: List[int] = []
    maxv = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((acc >> bits) & maxv)
    if pad and bits:
        ret.append((acc << (to_bits - bits)) & maxv)
    return ret


def bech32_encode(hrp: str, payload: bytes) -> str:
    data = convertbits(payload, 8, 5)
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(BECH32_CHARSET[d] for d in data + checksum)


def prepare_sdk_account_file(point_data_dir: Path, schema: str, account_count: int) -> Path:
    account_file = point_data_dir / "loadgen_sdk_accounts.jsonl"
    lines = []
    for i in range(account_count):
        digest = sha256(f"{schema}:loadgen-account:{i}".encode("utf-8")).digest()
        address = bech32_encode("hcp", digest[:20])
        lines.append(json.dumps({"name": f"loadgen{i}", "address": address}, ensure_ascii=False))
    account_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return account_file


def optional_db_counts(database_url: str, schema: str) -> Dict[str, int]:
    try:
        import psycopg2  # type: ignore
    except Exception:
        return {}
    counts: Dict[str, int] = {}
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            for table in ("accounts", "balances", "orders", "trades"):
                cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}";')
                counts[table] = int(cur.fetchone()[0])
    except Exception:
        return {}
    finally:
        conn.close()
    return counts


def stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        proc.terminate()
    else:
        proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def prepare_node_dirs(paths: Dict[str, Path], schema: str, engine: str, nodes: int, groups: int, endpoint: str) -> Path:
    point_data_dir = paths["data"] / schema
    if point_data_dir.exists():
        shutil.rmtree(point_data_dir)
    point_data_dir.mkdir(parents=True, exist_ok=True)
    for i in range(nodes):
        node_dir = point_data_dir / f"node{i}"
        node_dir.mkdir(parents=True, exist_ok=True)
        metadata = {
            "node_dir_type": "engine_sdk_backed_node",
            "note": "This records hcp-consensus/engine node state and, when HCP_ENGINE_SDK_EXEC=1, a Cosmos SDK-backed application store driven by engine commits.",
            "engine": engine,
            "node_index": i,
            "node_id": f"node-{i}",
            "groups": groups,
            "http_endpoint": endpoint,
        }
        (node_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return point_data_dir


def persist_node_statuses(point_data_dir: Path, engine_status: Dict[str, Any]) -> None:
    node_status = engine_status.get("node_status", {})
    for node_id, status in node_status.items():
        match = re.search(r"(\d+)$", node_id)
        node_name = f"node{match.group(1)}" if match else node_id.replace("-", "")
        node_dir = point_data_dir / node_name
        node_dir.mkdir(parents=True, exist_ok=True)
        (node_dir / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (point_data_dir / "cluster_status.json").write_text(
        json.dumps(engine_status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run_engine_loadgen_point(
    exp_name: str,
    report_dir: Path,
    point_name: str,
    engine: str,
    nodes: int,
    txs: int,
    target_tps: Optional[int] = None,
    groups: int = 0,
    loadgen_mode: str = "fixed",
    account_selection_mode: str = "random",
    zipf_alpha: Optional[float] = None,
    binaries: Optional[Dict[str, Path]] = None,
    paths: Optional[Dict[str, Path]] = None,
) -> Dict[str, Any]:
    paths = paths or ensure_dirs(exp_name, report_dir)
    binaries = binaries or stage_binaries(paths)
    database_url = os.environ.get("LOADGEN_DATABASE_URL", DEFAULT_DATABASE_URL)
    schema = sanitize(f"lg_{exp_name}_{point_name}")
    port = find_free_port()
    endpoint = f"http://127.0.0.1:{port}"
    bench_cmd = [str(binaries["bench"]), "serve", engine, str(nodes), f"127.0.0.1:{port}"]
    if groups > 0:
        bench_cmd.append(str(groups))

    point_data_dir = prepare_node_dirs(paths, schema, engine, nodes, groups, endpoint)
    account_count = env_int("LOADGEN_ACCOUNTS", 1000)
    sdk_account_file = prepare_sdk_account_file(point_data_dir, schema, account_count)
    server_log = paths["logs"] / f"{schema}_engine.log"
    loadgen_log = paths["logs"] / f"{schema}_loadgen.log"
    csv_path = paths["csv"] / f"{schema}_loadgen.csv"

    with server_log.open("w", encoding="utf-8") as slog:
        server_env = os.environ.copy()
        server_env.setdefault("HCP_ENGINE_SDK_EXEC", "1")
        server_env["HCP_ENGINE_NODE_DATA_DIR"] = str(point_data_dir)
        server_env.setdefault("HCP_ENGINE_SDK_CHAIN_ID", f"{schema}-chain")
        server_env["HCP_ENGINE_SDK_ACCOUNT_FILE"] = str(sdk_account_file)
        server_env["HCP_ENGINE_SDK_ACCOUNT_BALANCE"] = os.environ.get("LOADGEN_INITIAL_BALANCE", "1000000000")
        server_env["HCP_ENGINE_SDK_DENOM"] = os.environ.get("LOADGEN_DENOM", "uhcp")
        server = subprocess.Popen(
            bench_cmd,
            cwd=point_data_dir,
            stdout=slog,
            stderr=subprocess.STDOUT,
            text=True,
            env=server_env,
        )
    try:
        wait_http(f"{endpoint}/health")
        loadgen_cmd = [
            str(binaries["loadgen"]),
            "--protocol", "http",
            "--http-endpoint", f"{endpoint}/tx",
            "--mode", loadgen_mode,
            "--total-txs", str(txs),
            "--concurrency", os.environ.get("LOADGEN_CONCURRENCY", "64"),
            "--worker-threads", os.environ.get("LOADGEN_WORKERS", "4"),
            "--account-count", str(account_count),
            "--account-file", str(sdk_account_file),
            "--tx-encoding", os.environ.get("LOADGEN_TX_ENCODING", "proto"),
            "--initial-balance", os.environ.get("LOADGEN_INITIAL_BALANCE", "1000000000"),
            "--send-amount", os.environ.get("LOADGEN_SEND_AMOUNT", "1"),
            "--denom", os.environ.get("LOADGEN_DENOM", "uhcp"),
            "--payload-size", os.environ.get("LOADGEN_PAYLOAD_SIZE", "256"),
            "--account-selection-mode", account_selection_mode,
            "--database-url", database_url,
            "--db-schema", schema,
            "--reset-schema-on-start", "true",
            "--csv-path", str(csv_path),
            "--prometheus-addr", "127.0.0.1:0",
            "--json-interval-ms", "1000",
        ]
        if target_tps is not None and target_tps > 0:
            loadgen_cmd.extend(["--target-tps", str(target_tps)])
        if zipf_alpha is not None:
            loadgen_cmd.extend(["--zipf-alpha", str(zipf_alpha)])
        started = time.time()
        completed = subprocess.run(
            loadgen_cmd,
            cwd=PROJECT_ROOT / "hcp-loadgen",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=env_int("LOADGEN_TIMEOUT", 240),
        )
        duration_s = time.time() - started
        loadgen_log.write_text((completed.stdout or "") + "\n--- STDERR ---\n" + (completed.stderr or ""), encoding="utf-8")
        engine_status = wait_engine_complete(
            endpoint,
            txs,
            float(os.environ.get("ENGINE_COMPLETE_TIMEOUT", os.environ.get("ENGINE_DRAIN_SECONDS", "30"))),
        )
        persist_node_statuses(point_data_dir, engine_status)
        loadgen_snapshot = parse_last_json_line(completed.stdout)
        db_counts = optional_db_counts(database_url, schema)

        sample = engine_status.get("sample_status", {})
        network = engine_status.get("network", {})
        committed_txs = int(engine_status.get("committed_txs", sample.get("CommittedTxs", 0)))
        benchmark_tps = float(engine_status.get("benchmark_tps", 0.0))
        metrics = {
            "tps": benchmark_tps,
            "client_send_tps": float(loadgen_snapshot.get("actual_tps", 0.0)),
            "loadgen_cpu_percent": float(loadgen_snapshot.get("cpu_percent", 0.0)),
            "loadgen_mem_bytes": int(loadgen_snapshot.get("mem_bytes", 0)),
            "loadgen_p99_ms": float(loadgen_snapshot.get("latency_p99_ms", 0.0)),
            "success_rate": float(committed_txs) / float(txs) if txs > 0 else 0.0,
            "engine_tps": float(sample.get("TPS", 0.0)),
            "p50_ms": float(sample.get("P50LatencyMs", 0.0)),
            "p95_ms": float(sample.get("P95LatencyMs", 0.0)),
            "p99_ms": float(sample.get("P99LatencyMs", 0.0)),
            "messages": int(network.get("TotalMessages", 0)),
            "bytes": int(network.get("TotalBytes", 0)),
            "accepted_txs": int(engine_status.get("accepted_txs", 0)),
            "committed_txs": committed_txs,
            "completion_duration_s": float(engine_status.get("completion_duration_s", 0.0)),
            "db_trades": int(db_counts["trades"]) if "trades" in db_counts else None,
        }
        result = {
            "params": {
                "point": point_name,
                "engine": engine,
                "nodes": nodes,
                "groups": groups,
                "txs": txs,
                "target_tps": target_tps,
                "loadgen_mode": loadgen_mode,
                "account_selection_mode": account_selection_mode,
                "zipf_alpha": zipf_alpha,
                "payload_size": int(os.environ.get("LOADGEN_PAYLOAD_SIZE", "256")),
                "tx_encoding": os.environ.get("LOADGEN_TX_ENCODING", "proto"),
                "db_schema": schema,
            },
            "metrics": metrics,
            "duration_s": duration_s,
            "loadgen_exit_code": completed.returncode,
            "loadgen": loadgen_snapshot,
            "engine_status": engine_status,
            "db_counts": db_counts,
            "intermediate_paths": {
                "test_root": str(paths["root"]),
                "bin_dir": str(paths["bin"]),
                "data_dir": str(point_data_dir),
                "log_dir": str(paths["logs"]),
                "csv": str(csv_path),
            },
        }
        (report_dir / f"{sanitize(point_name)}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise RuntimeError(f"hcp-loadgen failed, see {loadgen_log}")
        return result
    finally:
        stop_process(server)


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_md(lines: List[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def aggregate_runs(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    vals = lambda key: [float(r["metrics"].get(key, 0.0)) for r in runs]
    return {
        "tps_mean": avg(vals("tps")),
        "tps_std": stdev(vals("tps")),
        "tps_ci": ci95(vals("tps")),
        "p50_mean": avg(vals("p50_ms")),
        "p50_std": stdev(vals("p50_ms")),
        "p50_ci": ci95(vals("p50_ms")),
        "p95_mean": avg(vals("p95_ms")),
        "p95_std": stdev(vals("p95_ms")),
        "p95_ci": ci95(vals("p95_ms")),
        "p99_mean": avg(vals("p99_ms")),
        "p99_std": stdev(vals("p99_ms")),
        "p99_ci": ci95(vals("p99_ms")),
        "msgs_mean": avg(vals("messages")),
        "msgs_std": stdev(vals("messages")),
        "bytes_mean": avg(vals("bytes")),
        "bytes_std": stdev(vals("bytes")),
        "loadgen_cpu_mean": avg(vals("loadgen_cpu_percent")),
        "loadgen_cpu_std": stdev(vals("loadgen_cpu_percent")),
        "loadgen_mem_mean": avg(vals("loadgen_mem_bytes")),
        "loadgen_mem_std": stdev(vals("loadgen_mem_bytes")),
        "success_rate_mean": avg(vals("success_rate")),
        "success_rate_std": stdev(vals("success_rate")),
        "raw": runs,
    }
