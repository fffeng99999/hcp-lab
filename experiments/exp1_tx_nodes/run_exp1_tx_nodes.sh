#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export NODES_LIST="${NODES_LIST:-4,8,16,32}"
export TX_LIST="${TX_LIST:-1000}"
export PORT_OFFSET="${PORT_OFFSET:-10}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp1}"

bash "$SCRIPT_DIR/test_exp1_tx_nodes.sh"
