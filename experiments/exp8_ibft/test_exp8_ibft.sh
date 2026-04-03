#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp8_ibft"
REPORT_OUT="experiments/exp8_ibft/report"

NODES_LIST="${NODES_LIST:-10,20,30,40,50}"
TARGET_TPS_LIST="${TARGET_TPS_LIST:-1000,3000,5000}"
TX_TOTAL="${TX_TOTAL:-5000}"
FAULTY_RATIO_LIST="${FAULTY_RATIO_LIST:-0,0.1,0.2}"

PORT_OFFSET="${PORT_OFFSET:-80}"
CHAIN_ID="${CHAIN_ID:-hcp-exp8}"
HCPD_BINARY="../$EXP_DIR/bin/hcpd"
CLI_BINARY="$EXP_DIR/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))

IBFT_BASE_LATENCY_MS="${IBFT_BASE_LATENCY_MS:-1}"
IBFT_JITTER_MS="${IBFT_JITTER_MS:-50}"
IBFT_TIMEOUT_MS="${IBFT_TIMEOUT_MS:-150}"
IBFT_MESSAGE_BYTES="${IBFT_MESSAGE_BYTES:-256}"
IBFT_MAX_ROUNDS="${IBFT_MAX_ROUNDS:-8}"

CONCURRENCY="${CONCURRENCY:-256}"
BATCH_SIZE="${BATCH_SIZE:-200}"
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
export IBFT_BASE_LATENCY_MS
export IBFT_JITTER_MS
export IBFT_TIMEOUT_MS
export IBFT_MESSAGE_BYTES
export IBFT_MAX_ROUNDS
export CLI_BINARY

echo "开始实验8：IBFT 性能建模"
echo "节点列表: $NODES_LIST"
echo "目标TPS列表: $TARGET_TPS_LIST"
echo "总交易数: $TX_TOTAL"
echo "故障率列表: $FAULTY_RATIO_LIST"
echo "链ID: $CHAIN_ID"
echo "端口偏移: $PORT_OFFSET (gRPC=$GRPC_PORT, RPC=$RPC_PORT)"
echo "负载参数: CONCURRENCY=$CONCURRENCY BATCH_SIZE=$BATCH_SIZE"
echo "IBFT参数: BASE_LATENCY_MS=$IBFT_BASE_LATENCY_MS JITTER_MS=$IBFT_JITTER_MS TIMEOUT_MS=$IBFT_TIMEOUT_MS MESSAGE_BYTES=$IBFT_MESSAGE_BYTES MAX_ROUNDS=$IBFT_MAX_ROUNDS"
echo "实验数据目录: $EXP_DIR"
echo "报告输出目录: $REPORT_OUT"

cd "$PROJECT_ROOT/hcp-loadgen"
echo "构建 hcp-loadgen..."
cargo build --release

cd "$PROJECT_ROOT/hcp-lab"
export EXP_ARTIFACT_ROOT="$EXP_DIR"
export PYTHONPATH="$PROJECT_ROOT/hcp-lab:${PYTHONPATH}"

python3 experiments/exp8_ibft/run_exp8.py \
  --nodes "$NODES_LIST" \
  --tps "$TARGET_TPS_LIST" \
  --tx "$TX_TOTAL" \
  --faulty-ratio "$FAULTY_RATIO_LIST" \
  --batch-size "$BATCH_SIZE" \
  --base-latency-ms "$IBFT_BASE_LATENCY_MS" \
  --jitter-ms "$IBFT_JITTER_MS" \
  --timeout-ms "$IBFT_TIMEOUT_MS" \
  --message-bytes "$IBFT_MESSAGE_BYTES" \
  --max-rounds "$IBFT_MAX_ROUNDS" \
  --out "$REPORT_OUT" \
  --loadgen-args "--protocol grpc --mode sustained --grpc-endpoint http://127.0.0.1:$GRPC_PORT --rpc-endpoint tcp://127.0.0.1:$RPC_PORT --chain-id $CHAIN_ID --keyring-backend test --keyring-home {data_root}/nodes_{nodes}/node1 --account-file {data_root}/nodes_{nodes}/accounts.jsonl --cli-binary $CLI_BINARY --send-amount 1 --fee-amount 1 --denom stake --account-count 100 --initial-nonce 0 --total-txs {tx} --target-tps {tps} --concurrency $CONCURRENCY --batch-size {batch_size} --metrics-interval 100 --json-interval-ms 100 --csv-path {data_root}/loadgen.csv"

