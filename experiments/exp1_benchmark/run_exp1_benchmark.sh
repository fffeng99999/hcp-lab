#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 实验特定参数（带默认值）
export NODES_LIST="${NODES_LIST:-8,16,32}"
export TX_COUNT="${TX_COUNT:-1000}"
export REPEAT="${REPEAT:-3}"
export OUTDIR="${OUTDIR:-$SCRIPT_DIR/../../../tests/exp1_benchmark}"

bash "$SCRIPT_DIR/test_exp1_benchmark.sh"
