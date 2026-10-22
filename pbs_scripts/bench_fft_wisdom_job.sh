#!/bin/bash
#PBS -N EOS26_fft_bench
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=64gb
#PBS -l walltime=1:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Time per r2c+c2r FFT pair with FFTW_ESTIMATE (EOS26.toml: USE_FFTW_WISDOM = false)
# and with the FFTW_PATIENT wisdom the v4.3_fftw scaling tests saved in
# <DATA_ROOT>/fftw_wisdoms, at the coeval FFT sizes of the scaling tests and of
# production (HII_DIM 1500), at the production thread count (scaling/bench_fft_wisdom.py).
# Decides whether the coeval phase should run with EOS26_RUN_FFTW_WISDOM=1.
# About 15-30 min; 14 GB at 1500.
# Usage: qsub pbs_scripts/bench_fft_wisdom_job.sh
#        qsub -v SIZES="300 1500",THREADS=16 pbs_scripts/bench_fft_wisdom_job.sh
# Output: logs/fft_bench_<jobid>.log

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

JID="${PBS_JOBID%%.*}"
THREADS="${THREADS:-16}"
SIZES="${SIZES:-200 300 400 500 1500}"
export OMP_NUM_THREADS="$THREADS" OMP_DYNAMIC=FALSE
unset OMP_PROC_BIND OMP_PLACES
mkdir -p logs

# shellcheck disable=SC2086  # SIZES is a list
uv run --no-sync --active --project "$ROOT" scaling/bench_fft_wisdom.py \
    --threads "$THREADS" --sizes $SIZES --repeat 3 2>&1 | tee "logs/fft_bench_${JID}.log"
