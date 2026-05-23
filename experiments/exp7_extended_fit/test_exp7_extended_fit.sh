#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
EXP7_NODES=8 EXP7_REPEAT=1 EXP7_TXS=50 python run_exp7_extended_fit.py pbft
