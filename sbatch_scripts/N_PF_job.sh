#!/bin/bash
#SBATCH -p RM-512
#SBATCH -t 12:00:00
#SBATCH -N 1
#SBATCH --ntasks-per-node=128
#SBATCH -o logs/PF_%j.bootstrap.out
#SBATCH -e logs/PF_%j.bootstrap.err


#echo commands to stdout
#set -x

module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

IDX="$1"
N="${2:-10}"

mkdir -p logs
LOG_OUT="logs/PF_${SLURM_JOB_ID}_zidx${IDX}_N${N}.out"
LOG_ERR="logs/PF_${SLURM_JOB_ID}_zidx${IDX}_N${N}.err"
LOG_LOG="logs/PF_${SLURM_JOB_ID}_zidx${IDX}_N${N}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

printf "IDX is: $IDX, N is: $N\n"
uv run run_scripts/run_N_PFs.py --z_idx_start "$IDX" --N "$N" --log-file "$LOG_LOG"
wait
