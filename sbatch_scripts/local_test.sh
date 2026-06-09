#!/bin/bash

JID="090626"
LOG_OUT="logs/full_test_${JID}.out"
LOG_ERR="logs/full_test_${JID}.err"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

echo "=========================================="
echo " Full test simulation  (job ${JID})"
echo "=========================================="

# ── Write test parameter template to disk ─────────────────────────────────────
# Overrides HII_DIM/DIM/BOX_LEN from EOS26.toml with test-box values
# (matching settings.TEST_HII_DIM=200, HIRES_TO_LOWRES_FACTOR=3, LOWRES_CELL_SIZE_MPC=1.666666)
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