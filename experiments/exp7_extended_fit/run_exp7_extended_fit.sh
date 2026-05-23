#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python run_exp7_extended_fit.py "$@"
