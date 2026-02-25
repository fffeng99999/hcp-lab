#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export GROUP_LIST="${GROUP_LIST:-32,16,8,4,2}"
export NODE_COUNT="${NODE_COUNT:-32}"
export TX_COUNT="${TX_COUNT:-10000}"
export REPEAT="${REPEAT:-5}"
export PORT_OFFSET="${PORT_OFFSET:-4000}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp4}"

bash "$SCRIPT_DIR/test_exp4_hierarchical.sh"
