#!/bin/bash 
#PBS -N scaling
#PBS -q normal
#PBS -l ncpus=32
#PBS -l mem=26gb
#PBS -l walltime=24:00:00
#PBS -l storage=scratch/qp00+gdata/qp00 
# Run 21cmFAST scaling measurements, then fit their scaling relations. 
# Usage: bash scaling/scaling_job.sh [HII_DIM ...] 

export PATH="$HOME/.local/bin:$PATH"
echo "NO EXPORT OMP PROC BIND, ON SCRATCH"
#export OMP_PROC_BIND="TRUE"
cd "$PBS_O_WORKDIR"
#cp -rf /scratch/qp00/$USER/EOS26 .
#cd EOS26
pwd

set -euo pipefail
#ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
ROOT="/scratch/qp00/$USER/EOS26"
#cd "$ROOT"
pwd

module purge
module load intel-compiler/2021.8.0
module load gsl/2.7.1
module load fftw3/3.3.10

module list

source /scratch/qp00/db9528/venvs/EOS26-intel/bin/activate
#rm -rf scaling/results/*.json

#uv sync \
#    --project "$ROOT" \
#    --frozen

ls
if [[ $# -eq 0 ]]; then
    dimensions=(200)
else
    dimensions=("$@")
fi

nthreads=(16)

#uv sync --frozen
for hii_dim in "${dimensions[@]}"; do
	for thread_num in "${nthreads[@]}"; do
        echo "=== Scaling measurement: HII_DIM=${hii_dim}, N_THREADS=${thread_num} ==="
	uv run --no-sync --active --project "$ROOT" \
    scaling/run_scaling.py \
    --hii-dim "$hii_dim" \
    --n-threads "$thread_num" \
    --template EOS26_wisdom.toml \
    --results-dir scaling/results/HII_DIM_200_wisdom_scaling
    done
done

#cp scaling/reports/* /scratch/qp00/db9528/EOS26/scaling/reports/
#echo "Reports: scaling/reports/"
