#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export K_LIST="${K_LIST:-1,2,4,8}"
export TX_LIST="${TX_LIST:-100,1000,10000}"
export REPEAT="${REPEAT:-5}"
export NODE_COUNT="${NODE_COUNT:-4,8,16,32}"
export PORT_OFFSET="${PORT_OFFSET:-3000}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp3}"
export LOADGEN_DB_ISOLATION="${LOADGEN_DB_ISOLATION:-true}"
export LOADGEN_DB_RESET="${LOADGEN_DB_RESET:-true}"
export LOADGEN_DB_SCHEMA_PREFIX="${LOADGEN_DB_SCHEMA_PREFIX:-exp3}"

bash "$SCRIPT_DIR/test_exp3_tpbft_parallel_block.sh"
