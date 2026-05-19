#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../" && pwd)"
BENCH_BIN="$PROJECT_ROOT/hcp-consensus-build/hcp-bench"

export NODES_LIST="${NODES_LIST:-8,16,32}"
export TX_COUNT="${TX_COUNT:-1000}"
export REPEAT="${REPEAT:-5}"
export OUTDIR="${OUTDIR:-$PROJECT_ROOT/tests/exp1_benchmark}"

mkdir -p "$OUTDIR"

echo "[EXP1] 基准对比实验"
echo "  NODES_LIST=$NODES_LIST TX_COUNT=$TX_COUNT REPEAT=$REPEAT"
echo "  OUTDIR=$OUTDIR"

IFS=',' read -ra NODES_ARRAY <<< "$NODES_LIST"
for NODES in "${NODES_ARRAY[@]}"; do
    echo "[EXP1] Running with NODES=$NODES"
    for ((r=1; r<=REPEAT; r++)); do
        echo "  Repeat $r/$REPEAT"
        "$BENCH_BIN" benchmark pbft "$NODES" "$TX_COUNT" "$OUTDIR/pbft_n${NODES}_r${r}.json"
        "$BENCH_BIN" benchmark tpbft "$NODES" "$TX_COUNT" "$OUTDIR/tpbft_n${NODES}_r${r}.json"
        "$BENCH_BIN" benchmark hotstuff "$NODES" "$TX_COUNT" "$OUTDIR/hotstuff_n${NODES}_r${r}.json"
        "$BENCH_BIN" benchmark raft "$NODES" "$TX_COUNT" "$OUTDIR/raft_n${NODES}_r${r}.json"
        "$BENCH_BIN" benchmark hierarchical_tpbft "$NODES" "$TX_COUNT" "$OUTDIR/hier_n${NODES}_r${r}.json"
    done
done

echo "[EXP1] 完成，数据保存在 $OUTDIR"
