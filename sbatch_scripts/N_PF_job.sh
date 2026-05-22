#!/bin/bash
#SBATCH -p RM-512
#SBATCH -t 12:00:00
#SBATCH -N 1
#SBATCH --ntasks-per-node=128
#SBATCH -o log/PF_%j.out
#SBATCH -e log/PF_%j.err


#echo commands to stdout
#set -x

module load fftw/3.3.8
module load gcc/13.2.1-p20240113   
module load openmpi/5.0.3-gcc13.2.1

uv sync --frozen

IDX="$1"
N="${2:-10}"

printf "IDX is: $IDX, N is: $N\n"&
uv run run_scripts/run_N_PFs.py --z_idx_start "$IDX" --N "$N"
wait
