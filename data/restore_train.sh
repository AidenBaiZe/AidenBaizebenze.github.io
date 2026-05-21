#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
cat train.json.part-* > train.json
echo "Restored data/train.json"
