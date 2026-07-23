#!/bin/bash 
#PBS -N scaling
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=20gb
#PBS -l walltime=3:00:00
#PBS -l jobfs=80gb
#PBS -l storage=scratch/qp00+gdata/qp00 
# Run 21cmFAST scaling measurements, then fit their scaling relations. 
# Usage: bash scaling/scaling_job.sh [HII_DIM ...] 

export PATH="$HOME/.local/bin:$PATH" 
#cd "$PBS_O_WORKDIR" 

set -euo pipefail 
#ROOT="$(cd "$PBS_O_WORKDIR" && pwd)" 
#cd "$ROOT"
module purge
module load intel-compiler/2021.8.0
module load gsl/2.7.1
module load fftw3/3.3.10

module list

ROOT="/scratch/qp00/$USER/EOS26"
source /scratch/qp00/db9528/venvs/EOS26-intel/bin/activate

#uv sync \
#    --project "$ROOT" \
#    --frozen

cd "$PBS_JOBFS"
pwd
ls
if [[ $# -eq 0 ]]; then
    dimensions=(100 200 300)
else
    dimensions=("$@")
fi

nthreads=(16)
cp -rf /scratch/qp00/$USER/EOS26 .
cd EOS26

#uv sync --frozen
for hii_dim in "${dimensions[@]}"; do
	for thread_num in "${nthreads[@]}"; do
        echo "=== Scaling measurement: HII_DIM=${hii_dim}, N_THREADS=${thread_num} ==="
        uv run --no-sync --active --project "$ROOT" scaling/run_scaling.py --hii-dim "$hii_dim" --n-threads "$thread_num"
        cp scaling/results/*.json /scratch/qp00/db9528/EOS26/scaling/results/
	rm -rf scaling/cache/HII_DIM_*
    done
done

#uv run --no-sync --active --project "$ROOT" scaling/run_scalingrelation.py

#cp scaling/reports/* /scratch/qp00/db9528/EOS26/scaling/reports/
#echo "Reports: scaling/reports/"
