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

N="${N:-3}"
JID="${PBS_JOBID%%.*}"

printf "N is: %s\n" "$N"
uv run --no-sync --active --project "$ROOT" run_scripts/run_N_coevals.py --N "$N" \
    --log-file "logs/EOS26_coeval_${N}_${JID}.log" \
    --compare
