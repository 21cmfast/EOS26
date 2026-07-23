#!/bin/bash
#PBS -N EOS26_PF_batch
#PBS -q RM-512
#PBS -l select=1:ncpus=128:mpiprocs=128
#PBS -l walltime=12:00:00
#PBS -o logs/PF.bootstrap.out
#PBS -e logs/PF.bootstrap.err

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

IDX="$1"
N="${2:-10}"

mkdir -p logs
JID="${PBS_JOBID%%.*}"
LOG_OUT="logs/PF_${JID}_zidx${IDX}_N${N}${TEST_SUFFIX}.out"
LOG_ERR="logs/PF_${JID}_zidx${IDX}_N${N}${TEST_SUFFIX}.err"
LOG_LOG="logs/PF_${JID}_zidx${IDX}_N${N}${TEST_SUFFIX}.log"
exec >"$LOG_OUT" 2>"$LOG_ERR"

uv sync --frozen

printf "IDX is: %s, N is: %s\n" "$IDX" "$N"
uv run run_scripts/run_N_PFs.py --z_idx_start "$IDX" --N "$N" --log-file "$LOG_LOG" $TEST_FLAG
wait