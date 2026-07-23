#!/bin/bash
#PBS -N EOS26_ICs
#PBS -q EM
#PBS -l select=1:ncpus=48:mpiprocs=48
#PBS -l walltime=20:00:00
#PBS -o logs/ICs.bootstrap.out
#PBS -e logs/ICs.bootstrap.err

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

module load fftw/3.3.8
module load gcc/13.2.1-p20240113
module load openmpi/5.0.3-gcc13.2.1

TEST_FLAG=""
TEST_SUFFIX=""
for arg in "$@"; do
    if [[ "$arg" == "--test" ]]; then
        TEST_FLAG="--test"
        TEST_SUFFIX="_test"
    fi
done

mkdir -p logs
JID="${PBS_JOBID%%.*}"
LOG_OUT="logs/ICs_${JID}${TEST_SUFFIX}.out"
LOG_ERR="logs/ICs_${JID}${TEST_SUFFIX}.err"
LOG_LOG="logs/ICs_${JID}${TEST_SUFFIX}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen
uv run run_scripts/run_ICs.py --log-file "$LOG_LOG" $TEST_FLAG