#!/bin/bash
#SBATCH -p EM
#SBATCH -t 20:00:00
#SBATCH --ntasks-per-node=48
#SBATCH -o logs/ICs_%j.bootstrap.out
#SBATCH -e logs/ICs_%j.bootstrap.err


#echo commands to stdout
#set -x

module load anaconda3/2024.10-1
module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

mkdir -p logs
LOG_OUT="logs/ICs_${SLURM_JOB_ID}.out"
LOG_ERR="logs/ICs_${SLURM_JOB_ID}.err"
LOG_LOG="logs/ICs_${SLURM_JOB_ID}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

uv run run_scripts/run_ICs.py --log-file "$LOG_LOG"
