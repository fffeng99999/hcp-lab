#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
BENCH_BIN="$PROJECT_ROOT/hcp-consensus-build/hcp-bench"

export NODES_LIST="${NODES_LIST:-16,32}"
export TX_COUNT="${TX_COUNT:-1000}"
export REPEAT="${REPEAT:-5}"
export OUTDIR="${OUTDIR:-$PROJECT_ROOT/tests/exp5_ablation}"

mkdir -p "$OUTDIR"

echo "[EXP5] 消融实验"
echo "  NODES_LIST=$NODES_LIST TX_COUNT=$TX_COUNT REPEAT=$REPEAT"

IFS=',' read -ra NODES_ARRAY <<< "$NODES_LIST"
for NODES in "${NODES_ARRAY[@]}"; do
    echo "[EXP5] Running ablation with NODES=$NODES"
    "$BENCH_BIN" ablation "$NODES" "$TX_COUNT" "$REPEAT" "$OUTDIR"
done

echo "[EXP5] 完成，数据保存在 $OUTDIR"
