#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export NODES_LIST="${NODES_LIST:-4,8,16,32}"
export TX_TOTAL="${TX_TOTAL:-1000}"
export PORT_OFFSET="${PORT_OFFSET:-10000}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp10}"
export LOADGEN_DB_ISOLATION="${LOADGEN_DB_ISOLATION:-true}"
export LOADGEN_DB_RESET="${LOADGEN_DB_RESET:-true}"
export LOADGEN_DB_SCHEMA_PREFIX="${LOADGEN_DB_SCHEMA_PREFIX:-exp10}"

bash "$SCRIPT_DIR/test_exp10_raft.sh"
