#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export COMETBFT_ORIGINAL_NODES="${COMETBFT_ORIGINAL_NODES:-4}"
export COMETBFT_ORIGINAL_TXS="${COMETBFT_ORIGINAL_TXS:-20}"
export COMETBFT_ORIGINAL_REPEAT="${COMETBFT_ORIGINAL_REPEAT:-1}"

python3 "$SCRIPT_DIR/run_cometbft_compare.py" "$@"
