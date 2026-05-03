#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export GROUP_LIST="${GROUP_LIST:-32,16,8,4,2}"
export SUB_CONSENSUS_LIST="${SUB_CONSENSUS_LIST:-pbft,raft}"
export SIG_ALGO_LIST="${SIG_ALGO_LIST:-bls,ed25519}"
export NODE_COUNT="${NODE_COUNT:-4}"
export TX_COUNT="${TX_COUNT:-100}"
export REPEAT="${REPEAT:-5}"
export PORT_OFFSET="${PORT_OFFSET:-13000}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp13}"
export LOADGEN_DB_ISOLATION="${LOADGEN_DB_ISOLATION:-true}"
export LOADGEN_DB_RESET="${LOADGEN_DB_RESET:-true}"
export LOADGEN_DB_SCHEMA_PREFIX="${LOADGEN_DB_SCHEMA_PREFIX:-exp13}"

bash "$SCRIPT_DIR/test_exp13.sh"
