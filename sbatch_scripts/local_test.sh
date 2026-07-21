#!/bin/bash

set -euo pipefail

JID="090626"
LOG_OUT="logs/full_test_${JID}.out"
LOG_ERR="logs/full_test_${JID}.err"
mkdir -p logs
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

echo "=========================================="
echo " Full test simulation  (job ${JID})"
echo "=========================================="

# ── Write test parameter template to disk ─────────────────────────────────────
# Uses the active EOS26.toml template with HII_DIM=200 and seed 42.
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

# ── Step 1: Initial conditions + perturbed fields ─────────────────────────────
echo ""
echo "=== Step 1/4: ICs ==="
uv run run_scripts/run_ICs.py \
    --log-file "logs/full_test_${JID}_ICs.log" \
    --test

# ── Step 2: Perturbed fields ─────────────────────────────
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

# ── Step 3: Perturbed halo fields ────────────────────────────────────────────
echo ""
echo "=== Step 3/4: PHFs ==="
uv run run_scripts/run_PHFs.py \
    --log-file "logs/full_test_${JID}_PHFs.log" \
    --test

# ── Step 4: Coevals ───────────────────────────────────────────────────────────
echo ""
echo "=== Step 4/4: Coevals ==="
uv run run_scripts/run_N_coevals.py \
    --log-file "logs/full_test_${JID}_coevals.log" \
    --N "-1" \
    --test

echo ""
echo "=== Full test simulation complete ==="

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

# ── Candidate comparison run ─────────────────────────────────────────────────
# --test --compare uses EOS26_test_HIIDIM200_compare/, leaving the reference
# cache above untouched. Lightcones are not included because no lightcone
# comparison check exists yet.
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