#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp1_tx_nodes"
REPORT_OUT="experiments/exp1_tx_nodes/report"
NODES_LIST="${NODES_LIST:-4,8,16}"
TX_LIST="${TX_LIST:-100}"
PORT_OFFSET="${PORT_OFFSET:-1000}"
HCPD_BINARY="../tests/exp1_tx_nodes/bin/hcpd"
CLI_BINARY="tests/exp1_tx_nodes/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))

export PORT_OFFSET
export HCPD_BINARY

cd "$PROJECT_ROOT/hcp-loadgen"
cargo build --release

cd "$PROJECT_ROOT/hcp-lab"
export EXP_ARTIFACT_ROOT="$EXP_DIR"
python3 experiments/exp1_tx_nodes/run_exp1.py \
  --nodes "$NODES_LIST" \
  --tx "$TX_LIST" \
  --out "$REPORT_OUT" \
  --loadgen-args "--protocol grpc --grpc-endpoint http://127.0.0.1:$GRPC_PORT --rpc-endpoint tcp://127.0.0.1:$RPC_PORT --chain-id hcp-testnet-1 --keyring-backend test --keyring-home $EXP_DIR/data/nodes_{nodes}/node1 --account-file $EXP_DIR/data/nodes_{nodes}/accounts.jsonl --cli-binary $CLI_BINARY --send-amount 1 --fee-amount 1 --denom stake --account-count 100 --initial-nonce 0 --total-txs {tx} --target-tps 100 --concurrency 32 --batch-size 1 --metrics-interval 100 --json-interval-ms 100 --csv-path $EXP_DIR/loadgen_nodes{nodes}_tx{tx}.csv"
