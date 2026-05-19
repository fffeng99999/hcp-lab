#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NODES="${NODES:-32}"
export TX_COUNT="${TX_COUNT:-1000}"
export OUTDIR="${OUTDIR:-$SCRIPT_DIR/../../../tests/exp4_group_scan}"
bash "$SCRIPT_DIR/test_exp4_group_scan.sh"
