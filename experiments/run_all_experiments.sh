#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================"
echo "HCP 论文第四章实验 - engine/loadgen 新流程"
echo "========================================"
echo "最终数据: $SCRIPT_DIR/exp*/report/"
echo "中间文件: $PROJECT_ROOT/tests/"

echo ""
echo "[1/6] 运行基准对比实验 (EXP1)"
bash "$SCRIPT_DIR/exp1_benchmark/test_exp1_benchmark.sh"

echo ""
echo "[2/6] 运行退化率计算 (EXP2，依赖EXP1)"
bash "$SCRIPT_DIR/exp2_degradation/test_exp2_degradation.sh"

echo ""
echo "[3/6] 运行饱和边界实验 (EXP3)"
bash "$SCRIPT_DIR/exp3_saturation/test_exp3_saturation.sh"

echo ""
echo "[4/6] 运行分组参数扫描 (EXP4)"
bash "$SCRIPT_DIR/exp4_group_scan/test_exp4_group_scan.sh"

echo ""
echo "[5/6] 运行消融实验 (EXP5)"
bash "$SCRIPT_DIR/exp5_ablation/test_exp5_ablation.sh"

echo ""
echo "[6/6] 运行性能界限建模 (EXP6，依赖EXP1+EXP5)"
bash "$SCRIPT_DIR/exp6_modeling/test_exp6_modeling.sh"

echo ""
echo "[汇总] 生成总报告..."
python3 "$SCRIPT_DIR/summarize_all.py"

echo ""
echo "========================================"
echo "全部实验完成"
echo "最终报告: $SCRIPT_DIR/*/report/"
echo "中间文件: $PROJECT_ROOT/tests/"
echo "========================================"
