#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
BENCH_BIN="$PROJECT_ROOT/hcp-consensus-build/hcp-bench"

export NODES="${NODES:-32}"
export TX_COUNT="${TX_COUNT:-1000}"
export OUTDIR="${OUTDIR:-$PROJECT_ROOT/tests/exp4_group_scan}"

mkdir -p "$OUTDIR"

echo "[EXP4] 分组参数扫描 (N=$NODES)"
"$BENCH_BIN" group-scan "$NODES" "$TX_COUNT" "$OUTDIR"

echo "[EXP4] 完成，数据保存在 $OUTDIR"
