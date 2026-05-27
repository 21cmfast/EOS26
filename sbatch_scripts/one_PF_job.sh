#!/bin/bash
#SBATCH -p RM-512
#SBATCH -t 2:00:00
#SBATCH -N 1
#SBATCH --ntasks-per-node=128
#SBATCH -o logs/PF_%j.bootstrap.out
#SBATCH -e logs/PF_%j.bootstrap.err

#echo commands to stdout
#set -x

module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

uv sync --frozen

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

IDX="$1"

mkdir -p logs
LOG_OUT="logs/PF_${SLURM_JOB_ID}_zidx${IDX}${TEST_SUFFIX}.out"
LOG_ERR="logs/PF_${SLURM_JOB_ID}_zidx${IDX}${TEST_SUFFIX}.err"
LOG_LOG="logs/PF_${SLURM_JOB_ID}_zidx${IDX}${TEST_SUFFIX}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

printf "IDX is: $IDX\n"
uv run run_scripts/run_PFs.py --z_idx "$IDX" --log-file "$LOG_LOG" $TEST_FLAG
wait
