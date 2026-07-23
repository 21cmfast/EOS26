#!/bin/bash

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

JID="090626"
LOG_OUT="logs/full_test_${JID}.out"
LOG_ERR="logs/full_test_${JID}.err"
mkdir -p logs
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

echo "=========================================="
echo " Full test simulation (job ${JID})"
echo "=========================================="

echo ""
echo "=== Writing test parameter template ==="
rm "test_template.toml"
uv run --no-sync 21cmfast template create \
    --param-file EOS26.toml \
    --mode minimal \
    --hii-dim 200 \
    --nodez.min 5.0 \
    --nodez.step 1.02 \
    --random-seed 42 \
    --out "test_template.toml"

echo ""
echo "=== Step 1/4: ICs ==="
uv run run_scripts/run_ICs.py \
    --log-file "logs/full_test_${JID}_ICs.log" \
    --test

echo ""
echo "=== Step 2/4: PFs ==="
uv run run_scripts/run_N_PFs.py \
    --z_idx_start 0 \
    --N "50" \
    --log-file "logs/full_test_${JID}_PFs.log" \
    --test

uv run run_scripts/run_N_PFs.py \
    --z_idx_start 50 \
    --N "-1" \
    --log-file "logs/full_test_${JID}_PFs.log" \
    --test

echo ""
echo "=== Step 3/4: PHFs ==="
uv run run_scripts/run_PHFs.py \
    --log-file "logs/full_test_${JID}_PHFs.log" \
    --test

echo ""
echo "=== Step 4/4: Coevals ==="
uv run run_scripts/run_N_coevals.py \
    --log-file "logs/full_test_${JID}_coevals.log" \
    --N "-1" \
    --test

echo ""
echo "=== Full test simulation complete ==="
echo ""
echo "=== Postprocessing: Lightcone ==="
uv run postprocess/make_lightcone.py \
    --log-file "logs/full_test_${JID}_lightcone.log" \
    --test

uv run postprocess/plot_lightcone.py \
    --log-file "logs/full_test_${JID}_lightcone.log" \
    --test

echo ""
echo "=== Comparing a new test simulation against the reference ==="

uv run run_scripts/run_ICs.py \
    --log-file "logs/full_test_${JID}_compare_ICs.log" \
    --test --compare

uv run run_scripts/run_N_PFs.py \
    --z_idx_start 0 \
    --N "50" \
    --log-file "logs/full_test_${JID}_compare_PFs.log" \
    --test --compare

uv run run_scripts/run_N_PFs.py \
    --z_idx_start 50 \
    --N "-1" \
    --log-file "logs/full_test_${JID}_compare_PFs.log" \
    --test --compare

uv run run_scripts/run_PHFs.py \
    --log-file "logs/full_test_${JID}_compare_PHFs.log" \
    --test --compare

uv run run_scripts/run_N_coevals.py \
    --log-file "logs/full_test_${JID}_compare_coevals.log" \
    --N "-1" \
    --test --compare

echo "=== Candidate comparison completed ==="