#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp6_alpenglow_votor"
REPORT_OUT="experiments/exp6_alpenglow_votor/report"
NODE_LIST="${NODE_LIST:-4,8,16,32}"
TX_COUNT="${TX_COUNT:-500}"
FAULTY_RATIO_LIST="${FAULTY_RATIO_LIST:-0,0.1,0.2}"
FAST_THRESHOLD="${FAST_THRESHOLD:-0.8}"
SLOW_THRESHOLD="${SLOW_THRESHOLD:-0.6}"
LOCAL_TIMEOUT_MS="${LOCAL_TIMEOUT_MS:-150}"
BATCH_SIZE="${BATCH_SIZE:-200}"
PORT_OFFSET="${PORT_OFFSET:-6000}"
CHAIN_ID="${CHAIN_ID:-hcp-exp6}"
HCPD_BINARY="../$EXP_DIR/bin/hcpd"
CLI_BINARY="$EXP_DIR/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))

export PORT_OFFSET
export CHAIN_ID
export HCPD_BINARY
export EXTRA_ACCOUNT_COUNT=100

echo "开始实验6：Alpenglow Votor 性能验证"
echo "节点列表: $NODE_LIST"
echo "交易数: $TX_COUNT"
echo "故障比例列表: $FAULTY_RATIO_LIST"
echo "快速路径阈值: $FAST_THRESHOLD"
echo "慢速路径阈值: $SLOW_THRESHOLD"
echo "本地超时(ms): $LOCAL_TIMEOUT_MS"
echo "批大小: $BATCH_SIZE"
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
python3 experiments/exp6_alpenglow_votor/run_exp6.py \
  --nodes "$NODE_LIST" \
  --tx "$TX_COUNT" \
  --faulty-ratio "$FAULTY_RATIO_LIST" \
  --fast-threshold "$FAST_THRESHOLD" \
  --slow-threshold "$SLOW_THRESHOLD" \
  --local-timeout-ms "$LOCAL_TIMEOUT_MS" \
  --batch-size "$BATCH_SIZE" \
  --out "$REPORT_OUT"
