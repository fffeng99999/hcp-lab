#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp4_hierarchical_consensus"
REPORT_OUT="experiments/exp4_hierarchical_consensus/report"
GROUP_LIST="${GROUP_LIST:-32,16,8,4,2}"
NODE_COUNT="${NODE_COUNT:-32}"
TX_COUNT="${TX_COUNT:-10000}"
REPEAT="${REPEAT:-5}"
PORT_OFFSET="${PORT_OFFSET:-4000}"
CHAIN_ID="${CHAIN_ID:-hcp-exp4}"
HCPD_BINARY="../$EXP_DIR/bin/hcpd"
CLI_BINARY="$EXP_DIR/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))

export PORT_OFFSET
export CHAIN_ID
export HCPD_BINARY
export EXTRA_ACCOUNT_COUNT=100

echo "开始实验4：分层共识通信复杂度与高频负载边界"
echo "组数列表: $GROUP_LIST"
echo "节点数: $NODE_COUNT"
echo "交易数: $TX_COUNT"
echo "重复次数: $REPEAT"
echo "链ID: $CHAIN_ID"
echo "端口偏移: $PORT_OFFSET (gRPC=$GRPC_PORT, RPC=$RPC_PORT)"
echo "实验目录: $EXP_DIR"
echo "hcpd: $HCPD_BINARY (loadgen cli: $CLI_BINARY)"
echo "报告输出目录: $REPORT_OUT"

cd "$PROJECT_ROOT/hcp-loadgen"
echo "构建 hcp-loadgen..."
cargo build --release

cd "$PROJECT_ROOT/hcp-lab"
export EXP_ARTIFACT_ROOT="$EXP_DIR"
export PYTHONPATH="$PROJECT_ROOT/hcp-lab:${PYTHONPATH}"
python3 experiments/exp4_hierarchical_consensus/run_exp4.py \
  --groups "$GROUP_LIST" \
  --nodes "$NODE_COUNT" \
  --tx "$TX_COUNT" \
  --repeat "$REPEAT" \
  --out "$REPORT_OUT" \
  --loadgen-args "--protocol grpc --grpc-endpoint http://127.0.0.1:$GRPC_PORT --rpc-endpoint tcp://127.0.0.1:$RPC_PORT --chain-id $CHAIN_ID --keyring-backend test --keyring-home {data_root}/nodes_{nodes}/node1 --account-file {data_root}/nodes_{nodes}/accounts.jsonl --cli-binary $CLI_BINARY --send-amount 1 --fee-amount 1 --denom stake --account-count 100 --initial-nonce 0 --total-txs {tx} --target-tps 5000 --concurrency 64 --batch-size 1 --metrics-interval 100 --json-interval-ms 100 --csv-path {data_root}/loadgen.csv"
