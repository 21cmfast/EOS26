#!/bin/bash
#PBS -N EOS26_rt_test
#PBS -q normal
#PBS -l ncpus=32
#PBS -l mem=64gb
#PBS -l walltime=3:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Recompute all coevals of the HII_DIM=200 reference (pbs_scripts/full_test_job.sh)
# with other run-time settings, and compare every coeval field with the reference:
#   RUN_THREADS (default 32)  -> EOS26_RUN_THREADS: OpenMP/FFTW threads of the C code
#   RUN_WISDOM  (default 1)   -> EOS26_RUN_FFTW_WISDOM: FFTW wisdom
# Neither is in the cache hash (run_scripts/sim_steps.py), so the reference's ICs, PFs
# and halo catalogs are read through symlinks; only the coevals are computed.
# Output: <DATA_ROOT>/EOS26_test_HIIDIM200_rt<threads>w<wisdom>_<jobid>/,
#         logs/HII_DIM200_reference/rt_test_<jobid>_{coevals,compare}.log
# Usage: qsub -W depend=afterok:<reference job id> pbs_scripts/test_runtime_settings_job.sh
#        qsub -v RUN_THREADS=32,RUN_WISDOM=0 pbs_scripts/test_runtime_settings_job.sh
# (request ncpus = RUN_THREADS)

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

JID="${PBS_JOBID%%.*}"
RUN_THREADS="${RUN_THREADS:-32}"
RUN_WISDOM="${RUN_WISDOM:-1}"
export OMP_DYNAMIC=FALSE
unset OMP_PROC_BIND OMP_PLACES

PYRUN=(uv run --no-sync --active --project "$ROOT")
SETTINGS=(python -c "import sys; sys.path.insert(0, 'run_scripts'); import settings; print(getattr(settings, sys.argv[1]))")
REF=$("${SETTINGS[@]}" CACHE_TEST_REFERENCE)
OUT="$("${SETTINGS[@]}" DATA_ROOT)/EOS26_test_HIIDIM200_rt${RUN_THREADS}w${RUN_WISDOM}_${JID}"
echo "reference: $REF"
echo "this test: $OUT  (threads $RUN_THREADS, wisdom $RUN_WISDOM)"

"${PYRUN[@]}" run_scripts/link_upstream.py "$REF" "$OUT" --test

EOS26_CACHE_DIR="$OUT" EOS26_RUN_THREADS="$RUN_THREADS" EOS26_RUN_FFTW_WISDOM="$RUN_WISDOM" \
OMP_NUM_THREADS="$RUN_THREADS" \
  "${PYRUN[@]}" run_scripts/run_N_coevals.py --N -1 --test \
    --log-file "logs/HII_DIM200_reference/rt_test_${JID}_coevals.log"

"${PYRUN[@]}" run_scripts/compare_caches.py "$REF" "$OUT" --test | tee "logs/HII_DIM200_reference/rt_test_${JID}_compare.log"
grep -h "done in" "logs/HII_DIM200_reference/rt_test_${JID}_coevals.log" | tail -n 3 || true
