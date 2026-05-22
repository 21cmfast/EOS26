#!/bin/bash -l
#PBS -l select=1:ncpus=16:ngpus=0:mem=128gb:mpiprocs=16
#PBS -q q02hal
#PBS -m bea
#PBS -M daniela.breitman@sns.it
#PBS -N EOS25-PFs
conda activate 21cmFASTv4
module load gcc/9.3.0
cd /home/dbreitman/EOS25/EOS25

printf "IDX is: $IDX \n"&
python run_PFs.py  --z_idx $IDX
wait
