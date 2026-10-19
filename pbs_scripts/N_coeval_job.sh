#!/bin/bash
#PBS -N EOS26_coeval
#PBS -q megamem
#PBS -l ncpus=16
#PBS -l mem=2990gb
#PBS -l walltime=48:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# Run a batch of N=8 (default) coeval boxes for the production-size EOS26 simulation with HII_DIM=1400.
# Usage: qsub pbs_scripts/N_coeval_job.sh [--N <N>]

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

export OMP_NUM_THREADS=16
export OMP_DYNAMIC=FALSE

unset OMP_PROC_BIND
unset OMP_PLACES

N="${N:-4}"
JID="${PBS_JOBID%%.*}"

printf "N is: %s\n" "$N"
uv run --no-sync --active --project "$ROOT" run_scripts/run_N_coevals.py --N "$N" \
    --log-file "logs/EOS26_coeval_${N}_${JID}.log" \
    --compare
