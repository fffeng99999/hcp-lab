#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
EXP_DIR="tests/exp3_parallel_merkle"
REPORT_OUT="experiments/exp3_parallel_merkle/report"
K_LIST="${K_LIST:-1,2,4,8}"
TX_LIST="${TX_LIST:-1000,5000,10000}"
TX_SIZE="${TX_SIZE:-512}"
REPEAT="${REPEAT:-30}"
NODE_COUNT="${NODE_COUNT:-1}"

echo "开始实验3：tPBFT 并行 Merkle Hash"
echo "k 列表: $K_LIST"
echo "交易数列表: $TX_LIST"
echo "交易大小(Bytes): $TX_SIZE"
echo "重复次数: $REPEAT"
echo "节点数: $NODE_COUNT"
echo "实验数据目录: $EXP_DIR"
echo "报告输出目录: $REPORT_OUT"

cd "$PROJECT_ROOT/hcp-lab"
export EXP_ARTIFACT_ROOT="$EXP_DIR"
export PYTHONPATH="$PROJECT_ROOT/hcp-lab:${PYTHONPATH}"
python3 experiments/exp3_parallel_merkle/run_exp3_tpbft_parallel.py \
  --k "$K_LIST" \
  --tx "$TX_LIST" \
  --size "$TX_SIZE" \
  --repeat "$REPEAT" \
  --nodes "$NODE_COUNT" \
  --out "$REPORT_OUT"
