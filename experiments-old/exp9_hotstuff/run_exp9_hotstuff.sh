#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export NODES_LIST="${NODES_LIST:-16,32,64,128,256}"
export TX_TOTAL="${TX_TOTAL:-100,1000,10000}"
export REPEAT="${REPEAT:-5}"
export FAULTY_RATIO_LIST="${FAULTY_RATIO_LIST:-0,0.1,0.2}"
export PORT_OFFSET="${PORT_OFFSET:-9000}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp9}"
export LOADGEN_DB_ISOLATION="${LOADGEN_DB_ISOLATION:-true}"
export LOADGEN_DB_RESET="${LOADGEN_DB_RESET:-true}"
export LOADGEN_DB_SCHEMA_PREFIX="${LOADGEN_DB_SCHEMA_PREFIX:-exp9}"

bash "$SCRIPT_DIR/test_exp9_hotstuff.sh"
