#!/bin/bash
#PBS -N EOS26_PFs
#PBS -q hugemem
#PBS -l ncpus=16
#PBS -l mem=600gb
#PBS -l walltime=48:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Run a batch of N=30 (default) PF boxes from starting index IDX
# for the production-size EOS26 simulation with HII_DIM=1400.
# Usage: qsub -F "<IDX> [N]" pbs_scripts/N_PF_job.sh

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

IDX="${1:?Error: IDX (starting z_idx) is required, e.g. qsub -F \"0 30\" pbs_scripts/N_PF_job.sh}"
N="${2:-30}"

printf "IDX is: %s, N is: %s\n" "$IDX" "$N"
uv run --no-sync --active --project "$ROOT" run_scripts/run_N_PFs.py \
    --z_idx_start "$IDX" \
    --N "$N" \
    --log-file "logs/EOS26_PFs_${IDX}_${JID}.log" \
    --compare
wait