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

source /scratch/qp00/db9528/venvs/EOS26-intel/bin/activate
set -euo pipefail

module purge
module load intel-compiler/2021.8.0
module load gsl/2.7.1
module load fftw3/3.3.10

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