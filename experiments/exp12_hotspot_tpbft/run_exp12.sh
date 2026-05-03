#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export GROUP_LIST="${GROUP_LIST:-32,16,8,4,2}"
export STRATEGY_LIST="${STRATEGY_LIST:-random,hotspot}"
export ZIPF_ALPHA_LIST="${ZIPF_ALPHA_LIST:-0.0,1.5,1.8,2.0}"
export SIG_ALGO_LIST="${SIG_ALGO_LIST:-bls,ed25519}"
export NODE_COUNT="${NODE_COUNT:-4}"
export TX_COUNT="${TX_COUNT:-100}"
export REPEAT="${REPEAT:-5}"
export PORT_OFFSET="${PORT_OFFSET:-12000}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp12}"
export LOADGEN_DB_ISOLATION="${LOADGEN_DB_ISOLATION:-true}"
export LOADGEN_DB_RESET="${LOADGEN_DB_RESET:-true}"
export LOADGEN_DB_SCHEMA_PREFIX="${LOADGEN_DB_SCHEMA_PREFIX:-exp12}"

bash "$SCRIPT_DIR/test_exp12.sh"
