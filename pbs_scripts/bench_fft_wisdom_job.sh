#!/bin/bash
#PBS -N EOS26_fft_bench
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=64gb
#PBS -l walltime=1:00:00
#PBS -l jobfs=1gb
#PBS -l storage=scratch/qp00+gdata/qp00

# Time per r2c+c2r FFT pair with FFTW_ESTIMATE (EOS26.toml: USE_FFTW_WISDOM = false)
# and with the FFTW_PATIENT wisdom the v4.3_fftw scaling tests saved in
# <DATA_ROOT>/fftw_wisdoms, at the coeval FFT sizes of the scaling tests and of
# production (HII_DIM 1500), at the production thread count. Decides whether the
# coeval phase should run with EOS26_RUN_FFTW_WISDOM=1. scaling/bench_fft_wisdom.c is
# compiled here against the modules the 21cmFAST venv is built with (scaling/config.sh).
# About 15-30 min; 14 GB at 1500.
# Usage: qsub pbs_scripts/bench_fft_wisdom_job.sh
#        qsub -v SIZES="300 1500",THREADS=16 pbs_scripts/bench_fft_wisdom_job.sh
# Output: scaling/logs/fft_bench_<jobid>.log

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
mkdir -p scaling/logs
LOG="scaling/logs/fft_bench_${JID}.log"
WISDOMS="${EOS26_WISDOMS:-$(python -c "import sys; sys.path.insert(0, 'run_scripts'); import settings; print(settings.DATA_ROOT)")/fftw_wisdoms}"

{
  echo "== how the 21cmFAST extension gets FFTW"
  EXT=$(python -c "import py21cmfast.c_21cmfast as c; print(c.__file__)")
  echo "$EXT"
  ldd "$EXT" | grep -iE "fftw|omp" || echo "  (no shared FFTW/OpenMP library: linked statically?)"
  echo "  fftwf_* symbols defined in the extension: $(nm -D --defined-only "$EXT" 2>/dev/null | grep -c ' fftwf_' || true)"
  echo "== wisdom files for $THREADS threads in $WISDOMS"
  ls -l "$WISDOMS"/*_NTHREADS"$THREADS" 2>/dev/null || echo "  none"

  CC="${CC:-icx}"
  case "$CC" in *icx*|*icc*) OMPFLAG=-qopenmp ;; *) OMPFLAG=-fopenmp ;; esac
  BIN="${PBS_JOBFS:-${TMPDIR:-/tmp}}/bench_fft_wisdom"
  echo "== $CC -O2 $OMPFLAG scaling/bench_fft_wisdom.c -lfftw3f_omp -lfftw3f -lm"
  "$CC" -O2 "$OMPFLAG" -o "$BIN" scaling/bench_fft_wisdom.c -lfftw3f_omp -lfftw3f -lm
  ldd "$BIN" | grep -iE "fftw|omp" || echo "  (FFTW linked statically)"
  echo
  # shellcheck disable=SC2086  # SIZES is a list
  "$BIN" "$WISDOMS" "$THREADS" 3 $SIZES
} 2>&1 | tee "$LOG"
