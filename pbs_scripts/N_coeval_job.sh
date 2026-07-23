#!/bin/bash
#PBS -N EOS26_coeval
#PBS -q EM
#PBS -l select=1:ncpus=96:mpiprocs=96
#PBS -l walltime=72:00:00
#PBS -o logs/coeval.bootstrap.out
#PBS -e logs/coeval.bootstrap.err

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

module load fftw/3.3.8
module load gcc/13.2.1-p20240113
module load openmpi/5.0.3-gcc13.2.1

POSITIONAL=()
TEST_FLAG=""
TEST_SUFFIX=""
for arg in "$@"; do
    case "$arg" in
        --test) TEST_FLAG="--test"; TEST_SUFFIX="_test" ;;
        *) POSITIONAL+=("$arg") ;;
    esac
done
set -- "${POSITIONAL[@]}"

N="${1:-10}"

mkdir -p logs
JID="${PBS_JOBID%%.*}"
LOG_OUT="logs/coeval_${JID}_N${N}${TEST_SUFFIX}.out"
LOG_ERR="logs/coeval_${JID}_N${N}${TEST_SUFFIX}.err"
LOG_LOG="logs/coeval_${JID}_N${N}${TEST_SUFFIX}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

printf "N is: %s\n" "$N"
uv run run_scripts/run_N_coevals.py --N "$N" --log-file "$LOG_LOG" $TEST_FLAG