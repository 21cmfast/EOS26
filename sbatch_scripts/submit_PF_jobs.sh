#!/bin/bash -l

TEST_FLAG=""
for arg in "$@"; do
    if [[ "$arg" == "--test" ]]; then
        TEST_FLAG="--test"
    fi
done

cd /jet/home/breitman/
for i in $(seq 0 91);
    do
    sbatch one_PF_job.sh "$i" $TEST_FLAG
    done
sleep 0.1

