#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
BENCH_BIN="$PROJECT_ROOT/hcp-consensus-build/hcp-bench"

export NODES="${NODES:-16}"
export OUTDIR="${OUTDIR:-$PROJECT_ROOT/tests/exp3_saturation}"

mkdir -p "$OUTDIR"

echo "[EXP3] 饱和边界初探 (N=$NODES)"

for engine in pbft tpbft hotstuff raft hierarchical_tpbft; do
    echo "[EXP3] Engine=$engine"
    "$BENCH_BIN" saturation "$engine" "$NODES" "$OUTDIR"
done

echo "[EXP3] 完成，数据保存在 $OUTDIR"
