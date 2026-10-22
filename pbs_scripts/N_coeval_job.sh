#!/bin/bash
#PBS -N EOS26_coeval
#PBS -q megamem
#PBS -l ncpus=16
#PBS -l mem=2990gb
#PBS -l walltime=48:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# Run a batch of N coeval boxes (default 4) for the production-size EOS26 simulation
# (EOS26.toml, HII_DIM=1500). It continues after the coevals already in the cache.
# Usage: qsub -v N=20 pbs_scripts/N_coeval_job.sh
#        qsub -v N=20,COMPARE=0 pbs_scripts/N_coeval_job.sh   # without the compare_EOS checks
#        qsub -l ncpus=32 -v N=20,EOS26_RUN_THREADS=32,EOS26_RUN_FFTW_WISDOM=1 pbs_scripts/N_coeval_job.sh
#          other threads / FFTW wisdom for the coevals only, without changing the cache
#          hash (run_scripts/sim_steps.py; check with pbs_scripts/test_runtime_settings_job.sh)
# Reads and writes the cache under /g/data (settings.CACHE_FULL); only logs go to logs/.

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"

set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"
pwd

# 21cmFAST environment: venv + modules (envs/use.sh; venv paths in scaling/config.sh).
# Default v4.3; submit with  qsub -v EOS26_VERSION=v4.2 ...  to use the old one.
EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

module list

JID="${PBS_JOBID%%.*}"

# N_THREADS = 16 in EOS26.toml, and it is part of the cache hash, so the template must
# keep it to find the existing ICs/PFs/halo catalogs. EOS26_RUN_THREADS changes only
# the threads the coevals run with (see run_scripts/sim_steps.py).
RUN_THREADS="${EOS26_RUN_THREADS:-16}"
if [[ -n "${PBS_NCPUS:-}" ]] && (( RUN_THREADS > PBS_NCPUS )); then
  echo "ERROR: EOS26_RUN_THREADS=$RUN_THREADS > ncpus=$PBS_NCPUS (qsub -l ncpus=...)" >&2; exit 1
fi
export OMP_NUM_THREADS="$RUN_THREADS"
export OMP_DYNAMIC=FALSE

unset OMP_PROC_BIND
unset OMP_PLACES

N="${N:-4}"
JID="${PBS_JOBID%%.*}"

# COMPARE=1 (default): compare_EOS checks after every coeval (file sizes, NaN/Inf,
# global means vs the HII_DIM=200 test reference). A failed check stops the job.
COMPARE="${COMPARE:-1}"
COMPARE_ARG=(); [[ "$COMPARE" == 1 ]] && COMPARE_ARG=(--compare)

printf "N is: %s, compare: %s\n" "$N" "$COMPARE"
uv run --no-sync --active --project "$ROOT" run_scripts/run_N_coevals.py --N "$N" \
    --log-file "logs/EOS26_coeval_${N}_${JID}.log" \
    ${COMPARE_ARG[@]+"${COMPARE_ARG[@]}"}
