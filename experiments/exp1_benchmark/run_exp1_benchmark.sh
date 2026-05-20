#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 实验1参数：默认与论文表3-4保持一致。
export EXP1_NODES="${EXP1_NODES:-8,16,32}"
export EXP1_TXS="${EXP1_TXS:-1000}"
export EXP_REPEAT="${EXP_REPEAT:-3}"

bash "$SCRIPT_DIR/test_exp1_benchmark.sh" "$@"
