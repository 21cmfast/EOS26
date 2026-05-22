#!/bin/bash -l

cd /jet/home/breitman/
for i in $(seq 0 91);
    do
    sbatch one_PF_job.sh "$i"
    done
sleep 0.1

