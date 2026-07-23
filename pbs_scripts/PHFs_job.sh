#!/bin/bash
#PBS -N EOS26_PHF
#PBS -q EM
#PBS -l select=1:ncpus=24:mpiprocs=24
#PBS -l walltime=72:00:00
#PBS -o logs/PHF.bootstrap.out
#PBS -e logs/PHF.bootstrap.err

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
LOG_OUT="logs/PHF_${JID}${TEST_SUFFIX}.out"
LOG_ERR="logs/PHF_${JID}${TEST_SUFFIX}.err"
LOG_LOG="logs/PHF_${JID}${TEST_SUFFIX}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen
uv run run_scripts/run_PHFs.py --log-file "$LOG_LOG" $TEST_FLAG
wait