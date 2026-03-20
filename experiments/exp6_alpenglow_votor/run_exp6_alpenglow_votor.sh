#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export NODE_LIST="${NODE_LIST:-4,8,16,32}"
export TX_COUNT="${TX_COUNT:-500}"
export FAULTY_RATIO_LIST="${FAULTY_RATIO_LIST:-0,0.1,0.2}"
export FAST_THRESHOLD="${FAST_THRESHOLD:-0.8}"
export SLOW_THRESHOLD="${SLOW_THRESHOLD:-0.6}"
export LOCAL_TIMEOUT_MS="${LOCAL_TIMEOUT_MS:-150}"
export BATCH_SIZE="${BATCH_SIZE:-200}"
export PORT_OFFSET="${PORT_OFFSET:-6000}"
export CHAIN_ID="${CHAIN_ID:-hcp-exp6}"

bash "$SCRIPT_DIR/test_exp6_alpenglow_votor.sh"
