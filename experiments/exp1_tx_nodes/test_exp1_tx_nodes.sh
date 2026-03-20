#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp1_tx_nodes"
REPORT_OUT="experiments/exp1_tx_nodes/report"
NODES_LIST="${NODES_LIST:-4,8,16}"
TX_LIST="${TX_LIST:-100}"
PORT_OFFSET="${PORT_OFFSET:-1000}"
CHAIN_ID="${CHAIN_ID:-hcp-exp1}"
HCPD_BINARY="../$EXP_DIR/bin/hcpd"
CLI_BINARY="$EXP_DIR/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))
TARGET_TPS="${TARGET_TPS:-300}"
CONCURRENCY="${CONCURRENCY:-128}"
BATCH_SIZE="${BATCH_SIZE:-8}"
COMET_TIMEOUT_COMMIT="${COMET_TIMEOUT_COMMIT:-500ms}"
COMET_SKIP_TIMEOUT_COMMIT="${COMET_SKIP_TIMEOUT_COMMIT:-true}"
COMET_MEMPOOL_RECHECK="${COMET_MEMPOOL_RECHECK:-false}"
COMET_TIMEOUT_PROPOSE="${COMET_TIMEOUT_PROPOSE:-3s}"
COMET_TIMEOUT_PREVOTE="${COMET_TIMEOUT_PREVOTE:-1s}"
COMET_TIMEOUT_PRECOMMIT="${COMET_TIMEOUT_PRECOMMIT:-1s}"

export PORT_OFFSET
export HCPD_BINARY
export CHAIN_ID
export EXTRA_ACCOUNT_COUNT=100
export COMET_TIMEOUT_COMMIT
export COMET_SKIP_TIMEOUT_COMMIT
export COMET_MEMPOOL_RECHECK
export COMET_TIMEOUT_PROPOSE
export COMET_TIMEOUT_PREVOTE
export COMET_TIMEOUT_PRECOMMIT

echo "开始实验1：交易量 × 节点规模"
echo "节点列表: $NODES_LIST"
echo "交易列表: $TX_LIST"
echo "链ID: $CHAIN_ID"
echo "端口偏移: $PORT_OFFSET (gRPC=$GRPC_PORT, RPC=$RPC_PORT)"
echo "负载参数: TARGET_TPS=$TARGET_TPS CONCURRENCY=$CONCURRENCY BATCH_SIZE=$BATCH_SIZE"
echo "共识参数: PROPOSE=$COMET_TIMEOUT_PROPOSE PREVOTE=$COMET_TIMEOUT_PREVOTE PRECOMMIT=$COMET_TIMEOUT_PRECOMMIT COMMIT=$COMET_TIMEOUT_COMMIT SKIP_TIMEOUT_COMMIT=$COMET_SKIP_TIMEOUT_COMMIT MEMPOOL_RECHECK=$COMET_MEMPOOL_RECHECK"
echo "实验数据目录: $EXP_DIR"
echo "报告输出目录: $REPORT_OUT"

cd "$PROJECT_ROOT/hcp-loadgen"
echo "构建 hcp-loadgen..."
cargo build --release

cd "$PROJECT_ROOT/hcp-lab"
export EXP_ARTIFACT_ROOT="$EXP_DIR"
export PYTHONPATH="$PROJECT_ROOT/hcp-lab:${PYTHONPATH}"
echo "启动实验执行器..."
python3 experiments/exp1_tx_nodes/run_exp1.py \
  --nodes "$NODES_LIST" \
  --tx "$TX_LIST" \
  --out "$REPORT_OUT" \
  --loadgen-args "--protocol grpc --grpc-endpoint http://127.0.0.1:$GRPC_PORT --rpc-endpoint tcp://127.0.0.1:$RPC_PORT --chain-id $CHAIN_ID --keyring-backend test --keyring-home {data_root}/nodes_{nodes}/node1 --account-file {data_root}/nodes_{nodes}/accounts.jsonl --cli-binary $CLI_BINARY --send-amount 1 --fee-amount 1 --denom stake --account-count 100 --initial-nonce 0 --total-txs {tx} --target-tps $TARGET_TPS --concurrency $CONCURRENCY --batch-size $BATCH_SIZE --metrics-interval 100 --json-interval-ms 100 --csv-path {data_root}/loadgen_nodes{nodes}_tx{tx}.csv"
