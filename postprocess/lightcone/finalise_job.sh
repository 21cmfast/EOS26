#!/bin/bash
#PBS -N EOS26_lightcone_finalise
#PBS -q normal
#PBS -l ncpus=12
#PBS -l mem=48gb
#PBS -l walltime=24:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# T_b with dv/dr and RSDs and a linked 21cmFAST lightcone file per geometry; then tau_21
# and the dv/dr-only T_b set aside in <out>/intermediate (not released)
# (postprocess/lightcone/finalise_lightcones.py, with tuesday). submit_lightcones.sh
# submits it after the per-quantity jobs. Works in blocks of ~8 GB; at HII_DIM=1500 it
# reads ~1.4 TB and writes ~0.9 TB (mostly the patch and the full sky). Resumable.
#
#   qsub postprocess/lightcone/finalise_job.sh
#   qsub -v TEST=1 postprocess/lightcone/finalise_job.sh
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR postprocess/lightcone/finalise_job.sh
# Env: EOS26_TEMPLATE (EOS26), TEST (0), RSDS (0 or 1 to override eos_lightcones.RSDS,
#      as the lightcones were made), DEGRADE_NSIDE (none), HEALPIX_NSIDE, ZMIN, ZMAX,
#      EOS26_LIGHTCONE_DIR, EXTRA_ARGS, EOS26_VERSION (v4.3_post).

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

EOS26_VERSION="${EOS26_VERSION:-v4.3_post}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

RUN="${EOS26_TEMPLATE:-EOS26}"
export EOS26_TEMPLATE="$RUN"
JID="${PBS_JOBID%%.*}"
ARGS=(--max-memory-gb 8)
[[ -n "${DEGRADE_NSIDE:-}" ]] && ARGS+=(--degrade-nside "$DEGRADE_NSIDE")
[[ -n "${HEALPIX_NSIDE:-}" ]] && ARGS+=(--healpix-nside "$HEALPIX_NSIDE")
[[ -n "${ZMIN:-}" ]] && ARGS+=(--zmin "$ZMIN")
[[ -n "${ZMAX:-}" ]] && ARGS+=(--zmax "$ZMAX")
case "${RSDS:-}" in 1) ARGS+=(--rsds) ;; 0) ARGS+=(--no-rsds) ;; esac   # unset: eos_lightcones.RSDS
LOGDIR="$ROOT/logs"; [[ "$RUN" != EOS26 ]] && LOGDIR="$ROOT/logs/$RUN"
TAG="${RUN}_lightcone"
if [[ "${TEST:-0}" == 1 ]]; then
  ARGS+=(--test); TAG="${RUN}_test_lightcone"; LOGDIR="$ROOT/logs/HII_DIM200_reference"
fi
# shellcheck disable=SC2206  # EXTRA_ARGS is a list of words
ARGS+=(${EXTRA_ARGS:-})
mkdir -p "$LOGDIR"
PY=(uv run --no-sync --active --project "$ROOT")
"${PY[@]}" postprocess/lightcone/finalise_lightcones.py "${ARGS[@]}" \
  --log-file "$LOGDIR/${TAG}_finalise_${JID}.log"
