#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

for name in article_sentence question_article sentences; do
  if ls "${name}.jsonl.part-"* >/dev/null 2>&1; then
    cat "${name}.jsonl.part-"* > "${name}.jsonl"
    echo "Restored ${name}.jsonl"
  fi
done
