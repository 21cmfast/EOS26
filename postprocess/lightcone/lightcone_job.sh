#!/bin/bash
#PBS -N EOS26_lightcone
#PBS -q normal
#PBS -l ncpus=12
#PBS -l mem=48gb
#PBS -l walltime=04:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Lightcones of ONE quantity (postprocess/lightcone/README.md). Normally submitted by
# submit_lightcones.sh, which picks the resources per geometry and quantity:
#
#   qsub -v QUANTITY=density postprocess/lightcone/lightcone_job.sh                  # rect + ring
#   qsub -v QUANTITY=density,GEOMETRY=healpix -l ncpus=48,mem=190gb,walltime=12:00:00 \
#        postprocess/lightcone/lightcone_job.sh
#   qsub -v QUANTITY=density,TEST=1 postprocess/lightcone/lightcone_job.sh            # HII_DIM=200 reference
#
# Resubmit the same job to resume: finished node intervals are skipped.
# Env: QUANTITY (required), GEOMETRY ("rect+ring"; any of rect ring healpix, joined by +),
#      NSIDE (2048), OVERSAMPLE (1), ORDER (ring), ZMIN (5), ZMAX (35), TEST (0),
#      PARTIAL (0; 1 = fill only the node intervals already cached),
#      EXTRA_ARGS (passed through), EOS26_VERSION (v4.3).

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

: "${QUANTITY:?set QUANTITY, e.g. qsub -v QUANTITY=density ...}"
GEOMETRY="${GEOMETRY:-rect ring}"
GEOMETRY="${GEOMETRY//+/ }"  # submit_lightcones.sh passes rect+ring (no spaces in qsub -v)
JID="${PBS_JOBID%%.*}"
THREADS="${PBS_NCPUS:-1}"
export OMP_NUM_THREADS="$THREADS"

ARGS=(--quantity "$QUANTITY" --geometry $GEOMETRY --threads "$THREADS"
      --zmin "${ZMIN:-5}" --zmax "${ZMAX:-35}")
if [[ " $GEOMETRY " == *" healpix "* ]]; then
  ARGS+=(--nside "${NSIDE:-2048}" --oversample "${OVERSAMPLE:-1}" --order "${ORDER:-ring}")
fi
TAG="EOS26"; LOGDIR="$ROOT/logs"
if [[ "${TEST:-0}" == 1 ]]; then
  ARGS+=(--test); TAG="full_test_lightcone"; LOGDIR="$ROOT/logs/HII_DIM200_reference"
fi
[[ "${PARTIAL:-0}" == 1 ]] && ARGS+=(--partial)
# shellcheck disable=SC2206  # EXTRA_ARGS is a list of words
ARGS+=(${EXTRA_ARGS:-})
LOG="$LOGDIR/${TAG}_lightcone_${QUANTITY}_${GEOMETRY// /_}_${JID}.log"

PY=(uv run --no-sync --active --project "$ROOT")
"${PY[@]}" postprocess/lightcone/lightcone_quantity.py "${ARGS[@]}" --log-file "$LOG"
