#!/bin/bash -l

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TEST_FLAG=""
for arg in "$@"; do
    if [[ "$arg" == "--test" ]]; then
        TEST_FLAG="--test"
    fi
done

for i in $(seq 0 91); do
    command=(qsub "$ROOT/pbs_scripts/one_PF_job.sh" "$i")
    if [[ -n "$TEST_FLAG" ]]; then
        command+=("$TEST_FLAG")
    fi
    "${command[@]}"
done