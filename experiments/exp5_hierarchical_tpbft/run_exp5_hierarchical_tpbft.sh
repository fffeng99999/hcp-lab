#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export GROUP_LIST="${GROUP_LIST:-32,16,8,4,2}"
export SIG_ALGO_LIST="${SIG_ALGO_LIST:-bls,ed25519}"
export NODE_COUNT="${NODE_COUNT:-32}"
export TX_COUNT="${TX_COUNT:-100}"
export REPEAT="${REPEAT:-5}"
export PORT_OFFSET="${PORT_OFFSET:-5000}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp5}"

bash "$SCRIPT_DIR/test_exp5_hierarchical_tpbft.sh"
