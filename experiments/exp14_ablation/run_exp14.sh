#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
LAB_ROOT="${PROJECT_ROOT}/hcp-lab"

cd "${LAB_ROOT}"

export PYTHONPATH="${LAB_ROOT}:${PYTHONPATH}"
export EXP_ARTIFACT_ROOT="${LAB_ROOT}/experiments/exp14_ablation/report/artifacts"
export CHAIN_ID="hcp-exp14"

python3 experiments/exp14_ablation/run_exp14.py "$@"
