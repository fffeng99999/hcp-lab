#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp3_parallel_merkle"
REPORT_OUT="experiments/exp3_parallel_merkle/report"
K_LIST="${K_LIST:-1,2,4,8}"
TX_LIST="${TX_LIST:-1000,5000,10000}"
REPEAT="${REPEAT:-30}"
NODE_COUNT="${NODE_COUNT:-1}"
PORT_OFFSET="${PORT_OFFSET:-3000}"
CHAIN_ID="${CHAIN_ID:-hcp-exp3}"
HCPD_BINARY="../$EXP_DIR/bin/hcpd"
CLI_BINARY="$EXP_DIR/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))

export PORT_OFFSET
export HCPD_BINARY
export CHAIN_ID
export EXTRA_ACCOUNT_COUNT=100

echo "开始实验3：tPBFT 并行 Merkle Hash（真实交易）"
echo "k 列表: $K_LIST"
echo "交易数列表: $TX_LIST"
echo "重复次数: $REPEAT"
echo "节点数: $NODE_COUNT"
echo "链ID: $CHAIN_ID"
echo "端口偏移: $PORT_OFFSET (gRPC=$GRPC_PORT, RPC=$RPC_PORT)"
echo "实验数据目录: $EXP_DIR"
echo "报告输出目录: $REPORT_OUT"

cd "$PROJECT_ROOT/hcp-loadgen"
echo "构建 hcp-loadgen..."
cargo build --release

cd "$PROJECT_ROOT/hcp-lab"
export EXP_ARTIFACT_ROOT="$EXP_DIR"
export PYTHONPATH="$PROJECT_ROOT/hcp-lab:${PYTHONPATH}"
python3 experiments/exp3_parallel_merkle/run_exp3_tpbft_parallel_block.py \
  --k "$K_LIST" \
  --tx "$TX_LIST" \
  --repeat "$REPEAT" \
  --nodes "$NODE_COUNT" \
  --out "$REPORT_OUT" \
  --loadgen-args "--protocol grpc --grpc-endpoint http://127.0.0.1:$GRPC_PORT --rpc-endpoint tcp://127.0.0.1:$RPC_PORT --chain-id $CHAIN_ID --keyring-backend test --keyring-home {data_root}/node1 --account-file {data_root}/accounts.jsonl --cli-binary $CLI_BINARY --send-amount 1 --fee-amount 1 --denom stake --account-count 100 --initial-nonce 0 --total-txs {tx} --target-tps 1000 --concurrency 32 --batch-size 1 --metrics-interval 100 --json-interval-ms 100 --csv-path {data_root}/loadgen.csv"
