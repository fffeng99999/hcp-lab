#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp13_lightweight_tpbft"
REPORT_OUT="experiments/exp13_lightweight_tpbft/report"
GROUP_LIST="${GROUP_LIST:-32,16,8,4,2}"
SUB_CONSENSUS_LIST="${SUB_CONSENSUS_LIST:-pbft,raft}"
SIG_ALGO_LIST="${SIG_ALGO_LIST:-bls,ed25519}"
NODE_COUNT="${NODE_COUNT:-16,32,64,128,256}"
TX_COUNT="${TX_COUNT:-100}"
REPEAT="${REPEAT:-5}"
PORT_OFFSET="${PORT_OFFSET:-13000}"
CHAIN_ID="${CHAIN_ID:-hcp-exp13}"
HCPD_BINARY="../$EXP_DIR/bin/hcpd"
CLI_BINARY="$EXP_DIR/bin/hcpd"
GRPC_PORT=$((9090 + PORT_OFFSET))
RPC_PORT=$((26657 + PORT_OFFSET))
LOADGEN_DB_ISOLATION="${LOADGEN_DB_ISOLATION:-true}"
LOADGEN_DB_RESET="${LOADGEN_DB_RESET:-true}"
LOADGEN_DB_SCHEMA_PREFIX="${LOADGEN_DB_SCHEMA_PREFIX:-exp13}"
LOADGEN_DATABASE_URL="${LOADGEN_DATABASE_URL:-}"

export PORT_OFFSET
export CHAIN_ID
export HCPD_BINARY
export EXTRA_ACCOUNT_COUNT=100
export LOADGEN_DB_ISOLATION
export LOADGEN_DB_RESET
export LOADGEN_DB_SCHEMA_PREFIX
export LOADGEN_DATABASE_URL

echo "========================================"
echo "开始实验13：子组轻量共识变体 TPBFT"
echo "========================================"
echo "组数列表: $GROUP_LIST"
echo "子层共识列表: $SUB_CONSENSUS_LIST"
echo "签名算法: $SIG_ALGO_LIST"
echo "节点数: $NODE_COUNT"
echo "交易数: $TX_COUNT"
echo "重复次数: $REPEAT"
echo "链ID: $CHAIN_ID"
echo "端口偏移: $PORT_OFFSET (gRPC=$GRPC_PORT, RPC=$RPC_PORT)"
echo "数据库隔离: ENABLED=$LOADGEN_DB_ISOLATION RESET=$LOADGEN_DB_RESET PREFIX=$LOADGEN_DB_SCHEMA_PREFIX DB_URL_OVERRIDE=${LOADGEN_DATABASE_URL:-<default>}"
echo "实验目录: $EXP_DIR"
echo "hcpd: $HCPD_BINARY (loadgen cli: $CLI_BINARY)"
echo "报告输出目录: $REPORT_OUT"
echo "========================================"

cd "$PROJECT_ROOT/hcp-loadgen"
echo "构建 hcp-loadgen..."
cargo build --release

cd "$PROJECT_ROOT/hcp-lab"
export EXP_ARTIFACT_ROOT="$EXP_DIR"
export PYTHONPATH="$PROJECT_ROOT/hcp-lab:${PYTHONPATH}"
python3 experiments/exp13_lightweight_tpbft/run_exp13.py \
  --groups "$GROUP_LIST" \
  --sub-consensuses "$SUB_CONSENSUS_LIST" \
  --sig-algos "$SIG_ALGO_LIST" \
  --nodes "$NODE_COUNT" \
  --tx "$TX_COUNT" \
  --repeat "$REPEAT" \
  --out "$REPORT_OUT"
