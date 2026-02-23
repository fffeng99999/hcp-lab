#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$PROJECT_ROOT/hcp-loadgen"
cargo build --release

cd "$PROJECT_ROOT/hcp-lab"
python3 main.py \
  --nodes "4,8,16,32" \
  --tx "100,500,1000" \
  --out "experiments/exp1_tx_nodes" \
  --loadgen-args "--protocol grpc --grpc-endpoint http://127.0.0.1:9090 --account-count 100 --total-txs {tx}"
