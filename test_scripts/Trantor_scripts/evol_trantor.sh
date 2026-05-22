#!/bin/bash -l
#PBS -l select=1:ncpus=16:ngpus=0:mem=300gb:mpiprocs=16
#PBS -q q02hal
#PBS -m bea
#PBS -M daniela.breitman@sns.it
#PBS -N EOS25-evol_state
conda activate 21cmFASTv4
module load gcc/9.3.0
cd /home/dbreitman/EOS25/EOS25

python -m memray run run_evol.py 
wait
