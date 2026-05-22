#!/bin/bash
#SBATCH -p EM
#SBATCH -t 72:00:00
#SBATCH --ntasks-per-node=24
#SBATCH -o log/PHF_%j.out
#SBATCH -e log/PHF_%j.err

#echo commands to stdout
#set -x

module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

uv sync --frozen

uv run run_PHFs.py 2>&1 | tee PHFs_output.txt
wait
