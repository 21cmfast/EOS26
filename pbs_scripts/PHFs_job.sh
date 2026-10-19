#!/bin/bash
#PBS -N EOS26_PHF
#PBS -q hugemem
#PBS -l ncpus=16
#PBS -l mem=1420gb
#PBS -l walltime=48:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Run PHFs for the production-size EOS26 simulation with HII_DIM=1400.
# Usage: qsub pbs_scripts/PHFs_job.sh

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

uv run --no-sync --active --project "$ROOT" run_scripts/run_PHFs.py \
    --log-file "logs/EOS26_PHFs_${JID}.log" \
    --compare
wait