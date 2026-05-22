#!/bin/bash
#SBATCH -p EM
#SBATCH -t 72:00:00
#SBATCH --ntasks-per-node=96
#SBATCH -o logs/coeval_%j.out
#SBATCH -e logs/coeval_%j.err


#echo commands to stdout
#set -x

module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

uv sync --frozen

uv run run_scripts/run_coeval.py
