#!/bin/bash -l

cd /home/dbreitman/EOS25
for i in $(seq 91 93);
    do
    qsub -v IDX=$i one_PF_trantor.sh
    done
sleep 0.1

