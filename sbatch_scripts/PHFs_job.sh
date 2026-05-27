#!/bin/bash
#SBATCH -p EM
#SBATCH -t 72:00:00
#SBATCH --ntasks-per-node=24
#SBATCH -o logs/PHF_%j.bootstrap.out
#SBATCH -e logs/PHF_%j.bootstrap.err

#echo commands to stdout
#set -x

module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

TEST_FLAG=""
TEST_SUFFIX=""
for arg in "$@"; do
    if [[ "$arg" == "--test" ]]; then
        TEST_FLAG="--test"
        TEST_SUFFIX="_test"
    fi
done

mkdir -p logs
LOG_OUT="logs/PHF_${SLURM_JOB_ID}${TEST_SUFFIX}.out"
LOG_ERR="logs/PHF_${SLURM_JOB_ID}${TEST_SUFFIX}.err"
LOG_LOG="logs/PHF_${SLURM_JOB_ID}${TEST_SUFFIX}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

uv run run_scripts/run_PHFs.py --log-file "$LOG_LOG" $TEST_FLAG
wait
