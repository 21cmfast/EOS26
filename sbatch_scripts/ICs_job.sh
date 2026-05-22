#!/bin/bash
#SBATCH -p EM
#SBATCH -t 20:00:00
#SBATCH --ntasks-per-node=48
#SBATCH -o logs/ICs_%j.out
#SBATCH -e logs/ICs_%j.err


#echo commands to stdout
#set -x

module load anaconda3/2024.10-1
module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

uv sync --frozen

uv run run_ICs_PFs.py 2>&1 | tee output.txt
