#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NODES="${NODES:-16}"
export OUTDIR="${OUTDIR:-$SCRIPT_DIR/../../../tests/exp3_saturation}"
bash "$SCRIPT_DIR/test_exp3_saturation.sh"
