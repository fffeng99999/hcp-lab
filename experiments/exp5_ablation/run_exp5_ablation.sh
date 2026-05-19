#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NODES_LIST="${NODES_LIST:-16,32}"
export TX_COUNT="${TX_COUNT:-1000}"
export REPEAT="${REPEAT:-3}"
export OUTDIR="${OUTDIR:-$SCRIPT_DIR/../../../tests/exp5_ablation}"
bash "$SCRIPT_DIR/test_exp5_ablation.sh"
