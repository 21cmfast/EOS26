#!/bin/bash
# Scaling campaign for 21cmFAST v4.2: peak memory per phase vs HII_DIM and N_THREADS.
#
#   bash scaling/campaign_v4.2.sh              # submit (idempotent; re-run to resume)
#   bash scaling/campaign_v4.2.sh --dry-run    # show what would be submitted
#   python3 scaling/summarize.py --label v4.2  # progress / results
#
# Any extra arguments are passed to scaling/launch.sh (e.g. --keep-sim).
# Results: scaling/results/v4.2/HII_DIM_XXXX_NT_YY/
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# A) HII_DIM scan (lever arm for the extrapolation to ~1400), at the production
#    thread count (16) and at a full Gadi node (48 cores).
DIMS_A="100 200 300 400 500"
THREADS_A="16 48"

# B) N_THREADS scan: memory vs threads (per-thread buffers) and speed-up.
#    The full range only where it is cheap; large boxes from 8 threads up.
PAIRS_B=""
for n in 1 2 4 8 16 24 32 48; do PAIRS_B+=" 200:$n"; done
for n in 8 16 24 32 48; do PAIRS_B+=" 400:$n"; done

# C) Optional larger box on hugemem (~300 GB, up to 48 h). Uncomment to add.
# PAIRS_C="600:48"
PAIRS_C=""

# D) Production-like batched coevals (run_N_coevals.py: a fresh process per 8
#    redshifts that re-reads the history from the cache). Both HII_DIM=1500
#    production OOM kills happened in such resumed batches, so check whether
#    batching raises the coeval peak compared with A. Results: ..._CB08/
PAIRS_D="200:16 300:16"
COEVAL_BATCH_D=8

bash "$HERE/launch.sh" --version v4.2 --dims "$DIMS_A" --threads "$THREADS_A" --pairs "$PAIRS_B $PAIRS_C" "$@"
bash "$HERE/launch.sh" --version v4.2 --pairs "$PAIRS_D" --coeval-batch "$COEVAL_BATCH_D" --no-preflight "$@"
