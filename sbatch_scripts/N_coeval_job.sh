#!/bin/bash
#SBATCH -p EM
#SBATCH -t 72:00:00
#SBATCH --ntasks-per-node=96
#SBATCH -o logs/coeval_%j.bootstrap.out
#SBATCH -e logs/coeval_%j.bootstrap.err


#echo commands to stdout
#set -x

module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

POSITIONAL=()
TEST_FLAG=""
TEST_SUFFIX=""
for arg in "$@"; do
    case "$arg" in
        --test) TEST_FLAG="--test"; TEST_SUFFIX="_test" ;;
        *)      POSITIONAL+=("$arg") ;;
    esac
done
set -- "${POSITIONAL[@]}"

N="${1:-10}"

mkdir -p logs
LOG_OUT="logs/coeval_${SLURM_JOB_ID}_N${N}${TEST_SUFFIX}.out"
LOG_ERR="logs/coeval_${SLURM_JOB_ID}_N${N}${TEST_SUFFIX}.err"
LOG_LOG="logs/coeval_${SLURM_JOB_ID}_N${N}${TEST_SUFFIX}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

printf "N is: $N\n"
uv run run_scripts/run_N_coevals.py --N "$N" --log-file "$LOG_LOG" $TEST_FLAG
