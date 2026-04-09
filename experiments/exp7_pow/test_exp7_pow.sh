#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp7_pow"
REPORT_OUT="experiments/exp7_pow/report"
NODE_LIST="${NODE_LIST:-4,8}"
DURATION="${DURATION:-100}"
REPEAT="${REPEAT:-1}"
DIFFICULTY="${DIFFICULTY:-8}"
TARGET_BLOCK_MS="${TARGET_BLOCK_MS:-2000}"
TX_PER_BLOCK="${TX_PER_BLOCK:-100}"
TARGET_TPS="${TARGET_TPS:-10}"
BATCH_SIZE="${BATCH_SIZE:-100}"
ORPHAN_BASE_RATE="${ORPHAN_BASE_RATE:-0.01}"
PORT_OFFSET="${PORT_OFFSET:-7000}"
CHAIN_ID="${CHAIN_ID:-hcp-exp7}"
HCPD_BINARY="../$EXP_DIR/bin/hcpd"
CLI_BINARY="$EXP_DIR/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))
LOADGEN_DB_ISOLATION="${LOADGEN_DB_ISOLATION:-true}"
LOADGEN_DB_RESET="${LOADGEN_DB_RESET:-true}"
LOADGEN_DB_SCHEMA_PREFIX="${LOADGEN_DB_SCHEMA_PREFIX:-exp7}"
LOADGEN_DATABASE_URL="${LOADGEN_DATABASE_URL:-}"

export PORT_OFFSET
export CHAIN_ID
export HCPD_BINARY
export EXTRA_ACCOUNT_COUNT=100
export LOADGEN_DB_ISOLATION
export LOADGEN_DB_RESET
export LOADGEN_DB_SCHEMA_PREFIX
export LOADGEN_DATABASE_URL

echo "开始实验7：PoW 节点扩展性与性能测试"
echo "节点列表: $NODE_LIST"
echo "运行时长(s): $DURATION"
echo "重复次数: $REPEAT"
echo "PoW 难度: $DIFFICULTY"
echo "目标出块时间(ms): $TARGET_BLOCK_MS"
echo "每块交易数: $TX_PER_BLOCK"
echo "目标发送TPS: $TARGET_TPS"
echo "批大小: $BATCH_SIZE"
echo "孤块基础概率: $ORPHAN_BASE_RATE"
echo "链ID: $CHAIN_ID"
echo "端口偏移: $PORT_OFFSET (gRPC=$GRPC_PORT, RPC=$RPC_PORT)"
echo "数据库隔离: ENABLED=$LOADGEN_DB_ISOLATION RESET=$LOADGEN_DB_RESET PREFIX=$LOADGEN_DB_SCHEMA_PREFIX DB_URL_OVERRIDE=${LOADGEN_DATABASE_URL:-<default>}"
echo "实验目录: $EXP_DIR"
echo "hcpd: $HCPD_BINARY (loadgen cli: $CLI_BINARY)"
echo "报告输出目录: $REPORT_OUT"

cd "$PROJECT_ROOT/hcp-loadgen"
echo "构建 hcp-loadgen..."
cargo build --release

cd "$PROJECT_ROOT/hcp-lab"
export EXP_ARTIFACT_ROOT="$EXP_DIR"
export PYTHONPATH="$PROJECT_ROOT/hcp-lab:${PYTHONPATH}"
python3 experiments/exp7_pow/run_exp7.py \
  --nodes "$NODE_LIST" \
  --duration "$DURATION" \
  --repeat "$REPEAT" \
  --difficulty "$DIFFICULTY" \
  --target-block-ms "$TARGET_BLOCK_MS" \
  --tx-per-block "$TX_PER_BLOCK" \
  --target-tps "$TARGET_TPS" \
  --batch-size "$BATCH_SIZE" \
  --orphan-base-rate "$ORPHAN_BASE_RATE" \
  --out "$REPORT_OUT"
