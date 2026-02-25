#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp2_storage_share"
REPORT_OUT="experiments/exp2_storage_share/report"
SHARES="${SHARES:-2,4,8,16}"
NODE_COUNT="${NODE_COUNT:-32}"
TX_COUNT="${TX_COUNT:-10000}"
REPEAT="${REPEAT:-3}"
PORT_OFFSET="${PORT_OFFSET:-2000}"
CHAIN_ID="${CHAIN_ID:-hcp-exp2}"
HCPD_BINARY="../tests/exp2_storage_share/bin/hcpd"
CLI_BINARY="tests/exp2_storage_share/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))

export PORT_OFFSET
export HCPD_BINARY
export CHAIN_ID

echo "开始实验2：共享存储规模变化对共识吞吐的影响"
echo "共享规模: $SHARES"
echo "节点数: $NODE_COUNT"
echo "交易数: $TX_COUNT"
echo "重复次数: $REPEAT"
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
echo "启动实验执行器..."
python3 experiments/exp2_storage_share/run_exp2.py \
  --shares "$SHARES" \
  --nodes "$NODE_COUNT" \
  --tx "$TX_COUNT" \
  --repeat "$REPEAT" \
  --out "$REPORT_OUT" \
  --loadgen-args "--protocol grpc --grpc-endpoint http://127.0.0.1:$GRPC_PORT --rpc-endpoint tcp://127.0.0.1:$RPC_PORT --chain-id $CHAIN_ID --keyring-backend test --keyring-home {data_root}/nodes_{nodes}/node1 --account-file {data_root}/nodes_{nodes}/accounts.jsonl --cli-binary $CLI_BINARY --send-amount 1 --fee-amount 1 --denom stake --account-count 100 --initial-nonce 0 --total-txs {tx} --target-tps 1000 --concurrency 32 --batch-size 1 --metrics-interval 100 --json-interval-ms 100 --csv-path {data_root}/loadgen.csv"
