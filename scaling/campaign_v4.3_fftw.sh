#!/bin/bash
# FFTW wisdom test: 21cmFAST 4.3.1 with USE_FFTW_WISDOM = true (label v4.3_fftw),
# to compare with the same configurations of v4.3_patch (same code, no wisdom).
#
#   bash scaling/campaign_v4.3_fftw.sh --dry-run
#   bash scaling/campaign_v4.3_fftw.sh --follow
#   python3 scaling/summarize.py --label v4.3_fftw
#
# The first phase of each (HII_DIM, N_THREADS) makes the FFTW_PATIENT plans for its
# two FFT sizes (DIM^3 and HII_DIM^3) and saves them to /g/data/qp00/$USER/fftw_wisdoms
# (run_scripts/sim_steps.py; $EOS26_WISDOMS overrides); later phases load them. So the ICs phase includes
# the one-off planning cost, and PF/PHF/coeval show the speed-up. The planning time
# at DIM = 600, 900, 1200, 1500 is what to extrapolate to production (DIM = 4500).
# Results: scaling/results/v4.3_fftw/HII_DIM_XXXX_NT_YY/
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAIRS="200:16 300:16 400:16 400:32 500:16"
bash "$HERE/launch.sh" --version v4.3_fftw --pairs "$PAIRS" "$@"
