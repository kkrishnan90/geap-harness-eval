#!/usr/bin/env bash
# What CI runs for every merge request touching checkout-deploy.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
echo "== validator unit tests"
python3 -m unittest discover -s tests -t . -q
echo "== policy check"
python3 -m policy deploy
