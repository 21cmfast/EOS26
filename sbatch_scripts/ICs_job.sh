#!/bin/bash
#SBATCH -p EM
#SBATCH -t 20:00:00
#SBATCH --ntasks-per-node=48
#SBATCH -o logs/ICs_%j.bootstrap.out
#SBATCH -e logs/ICs_%j.bootstrap.err


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
LOG_OUT="logs/ICs_${SLURM_JOB_ID}${TEST_SUFFIX}.out"
LOG_ERR="logs/ICs_${SLURM_JOB_ID}${TEST_SUFFIX}.err"
LOG_LOG="logs/ICs_${SLURM_JOB_ID}${TEST_SUFFIX}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

# Write EOS26.toml with node_redshifts and random_seed embedded
uv run 21cmfast template create \
    --param-file EOS26.toml \
    --mode full \
    --nodez.min 5.0 \
    --nodez.step 1.02 \
    --random-seed 42 \
    --out EOS26.toml

# Write minimal template (reads node_redshifts from EOS26.toml already written above)
uv run 21cmfast template create \
    --param-file EOS26.toml \
    --mode minimal \
    --out EOS26_minimal.toml

uv run run_scripts/run_ICs.py --log-file "$LOG_LOG" $TEST_FLAG
