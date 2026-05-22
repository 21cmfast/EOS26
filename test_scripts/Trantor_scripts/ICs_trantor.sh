#!/bin/bash -l
#PBS -l select=1:ncpus=16:ngpus=0:mem=128gb:mpiprocs=16
#PBS -q q02hal
#PBS -m bea
#PBS -M daniela.breitman@sns.it
#PBS -N EOS25-ICs
conda activate 21cmFASTv4
module load gcc/9.3.0
cd /home/dbreitman/EOS25/EOS25
21cmfast run ics --param-file EOS25.toml --seed 1234 --cachedir "/home/dbreitman/EOS25/TEST_L600_HIIDIM400_DIM1200_NO_PERTURN_ON_HIGH_RES" --hii-dim 400 --dim 1200 --box-len 600
wait
