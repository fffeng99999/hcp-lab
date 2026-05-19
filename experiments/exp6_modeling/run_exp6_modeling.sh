#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export OUTDIR="${OUTDIR:-$SCRIPT_DIR/../../../tests/exp6_modeling}"
bash "$SCRIPT_DIR/test_exp6_modeling.sh"
