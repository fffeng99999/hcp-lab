#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================"
echo "HCP 第三章实验总入口（exp0-exp6）"
echo "========================================"
echo "最终数据: $SCRIPT_DIR/exp*/report/"
echo "中间文件: $PROJECT_ROOT/tests/"

echo ""
echo "[1/7] 运行 CometBFT 原版与 CometBFT-light 对比 (EXP0)"
bash "$SCRIPT_DIR/exp0_cometbft_compare/test_cometbft_compare.sh"

echo ""
echo "[2/7] 运行基准对比实验 (EXP1)"
bash "$SCRIPT_DIR/exp1_benchmark/test_exp1_benchmark.sh"

echo ""
echo "[3/7] 运行规模退化率计算 (EXP2，依赖 EXP1)"
bash "$SCRIPT_DIR/exp2_degradation/test_exp2_degradation.sh"

echo ""
echo "[4/7] 运行饱和点扫描实验 (EXP3)"
bash "$SCRIPT_DIR/exp3_saturation/test_exp3_saturation.sh"

echo ""
echo "[5/7] 运行分组参数扫描 (EXP4)"
bash "$SCRIPT_DIR/exp4_group_scan/test_exp4_group_scan.sh"

echo ""
echo "[6/7] 运行消融实验 (EXP5)"
bash "$SCRIPT_DIR/exp5_ablation/test_exp5_ablation.sh"

echo ""
echo "[7/7] 运行性能边界建模 (EXP6，依赖 EXP1+EXP5)"
bash "$SCRIPT_DIR/exp6_modeling/test_exp6_modeling.sh"

echo ""
echo "[SUMMARY] 生成总报告..."
python3 "$SCRIPT_DIR/summarize_all.py"

echo ""
echo "========================================"
echo "全部实验完成"
echo "最终报告: $SCRIPT_DIR/report/summary_all.md"
echo "中间文件: $PROJECT_ROOT/tests/"
echo "========================================"
