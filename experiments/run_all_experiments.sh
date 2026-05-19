#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TESTS_DIR="$PROJECT_ROOT/tests"

echo "========================================"
echo "HCP 论文第四章实验 - 全量运行"
echo "========================================"

# 可选：清理旧数据
if [ "${CLEAN:-false}" = "true" ]; then
    echo "[INFO] 清理旧数据..."
    rm -rf "$TESTS_DIR"/exp*
fi

mkdir -p "$TESTS_DIR"

# 运行独立实验（有依赖的后面再跑）
echo ""
echo "[1/6] 运行基准对比实验 (EXP1)"
bash "$SCRIPT_DIR/exp1_benchmark/test_exp1_benchmark.sh"

echo ""
echo "[2/6] 运行饱和边界实验 (EXP3)"
bash "$SCRIPT_DIR/exp3_saturation/test_exp3_saturation.sh"

echo ""
echo "[3/6] 运行分组参数扫描 (EXP4)"
bash "$SCRIPT_DIR/exp4_group_scan/test_exp4_group_scan.sh"

echo ""
echo "[4/6] 运行消融实验 (EXP5)"
bash "$SCRIPT_DIR/exp5_ablation/test_exp5_ablation.sh"

# 运行依赖实验（依赖前面数据）
echo ""
echo "[5/6] 运行退化率计算 (EXP2，依赖EXP1)"
bash "$SCRIPT_DIR/exp2_degradation/test_exp2_degradation.sh"

echo ""
echo "[6/6] 运行性能界限建模 (EXP6，依赖EXP1+EXP5)"
bash "$SCRIPT_DIR/exp6_modeling/test_exp6_modeling.sh"

# 汇总所有数据
echo ""
echo "[汇总] 生成总报告..."
python3 "$SCRIPT_DIR/summarize_all.py"

echo ""
echo "========================================"
echo "全部实验完成！"
echo "中间数据: $TESTS_DIR"
echo "实验报告: $SCRIPT_DIR/*/report/"
echo "总汇总  : $TESTS_DIR/summary_all.md"
echo "========================================"
