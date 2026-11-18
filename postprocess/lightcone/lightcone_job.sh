#!/bin/bash
#PBS -N EOS26_lightcone
#PBS -q normal
#PBS -l ncpus=12
#PBS -l mem=48gb
#PBS -l walltime=04:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# Lightcones of ONE quantity, made with tuesday (postprocess/lightcone/README.md).
# Normally submitted by submit_lightcones.sh, which picks the resources per geometry:
#
#   qsub -v QUANTITY=density postprocess/lightcone/lightcone_job.sh        # rect + angular plane
#   qsub -v QUANTITY=density,GEOMETRY=healpix -l ncpus=48,mem=190gb,walltime=12:00:00 \
#        postprocess/lightcone/lightcone_job.sh
#   qsub -v QUANTITY=density,TEST=1 postprocess/lightcone/lightcone_job.sh             # HII_DIM=200 test
#   qsub -v QUANTITY=density,EOS26_TEMPLATE=EOS26_earlyEoR postprocess/lightcone/lightcone_job.sh
#
# Resubmit the same job to resume: what is complete is skipped.
# Env: QUANTITY (required), GEOMETRY ("rect+angular_plane"; any of rect angular_plane
#      healpix patch, joined by +), EOS26_TEMPLATE (EOS26; the run), TEST (0), PARTIAL (0; 1 = fill only the node
#      intervals already cached), ZMIN, ZMAX, HEALPIX_NSIDE, PATCH_NSIDE (defaults in
#      eos_lightcones.py), EOS26_LIGHTCONE_DIR (output root), EXTRA_ARGS (passed through),
#      EOS26_VERSION (v4.3_post: 21cmFAST >= 4.3.2 + tuesday).
# Overrides of the choices in eos_lightcones.py (all jobs of a run must agree): RSDS (0 or
#      1), ROTATION ('SEQ:a+b+c' or none; + for the commas, which qsub -v cannot carry),
#      PATCH_CENTER ('LON+LAT').

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

EOS26_VERSION="${EOS26_VERSION:-v4.3_post}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

: "${QUANTITY:?set QUANTITY, e.g. qsub -v QUANTITY=density ...}"
GEOMETRY="${GEOMETRY:-rect angular_plane}"
GEOMETRY="${GEOMETRY//+/ }"  # submit_lightcones.sh passes rect+angular_plane (no spaces in qsub -v)
RUN="${EOS26_TEMPLATE:-EOS26}"
export EOS26_TEMPLATE="$RUN"
JID="${PBS_JOBID%%.*}"
THREADS="${PBS_NCPUS:-1}"
# the threads are Python threads around single-threaded sampling: no nested threading
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1

ARGS=(--quantity "$QUANTITY" --geometry $GEOMETRY --threads "$THREADS")
[[ -n "${ZMIN:-}" ]] && ARGS+=(--zmin "$ZMIN")
[[ -n "${ZMAX:-}" ]] && ARGS+=(--zmax "$ZMAX")
[[ -n "${HEALPIX_NSIDE:-}" ]] && ARGS+=(--healpix-nside "$HEALPIX_NSIDE")
[[ -n "${PATCH_NSIDE:-}" ]] && ARGS+=(--patch-nside "$PATCH_NSIDE")
[[ "${PARTIAL:-0}" == 1 ]] && ARGS+=(--partial)
case "${RSDS:-}" in 1) ARGS+=(--rsds) ;; 0) ARGS+=(--no-rsds) ;; esac   # unset: eos_lightcones.RSDS
[[ -n "${ROTATION:-}" ]] && ARGS+=(--rotation "${ROTATION//+/,}")
# shellcheck disable=SC2206  # two numbers
[[ -n "${PATCH_CENTER:-}" ]] && ARGS+=(--patch-center ${PATCH_CENTER//+/ })
LOGDIR="$ROOT/logs"; [[ "$RUN" != EOS26 ]] && LOGDIR="$ROOT/logs/$RUN"
TAG="${RUN}_lightcone"
if [[ "${TEST:-0}" == 1 ]]; then
  ARGS+=(--test); TAG="${RUN}_test_lightcone"; LOGDIR="$ROOT/logs/HII_DIM200_reference"
fi
# shellcheck disable=SC2206  # EXTRA_ARGS is a list of words
ARGS+=(${EXTRA_ARGS:-})
mkdir -p "$LOGDIR"
LOG="$LOGDIR/${TAG}_${QUANTITY}_${GEOMETRY// /_}_${JID}.log"

PY=(uv run --no-sync --active --project "$ROOT")
"${PY[@]}" postprocess/lightcone/lightcone_quantity.py "${ARGS[@]}" --log-file "$LOG"
