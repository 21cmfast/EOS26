#!/bin/bash
#PBS -N EOS26_lightcone_finalise
#PBS -q normal
#PBS -l ncpus=8
#PBS -l mem=32gb
#PBS -l walltime=04:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# dv/dr-corrected brightness temperature + index files of the lightcones
# (postprocess/lightcone/finalise_lightcones.py). submit_lightcones.sh submits it after
# the per-quantity jobs. Reads brightness_temp, tau_21 and los_velocity in blocks of
# ~2 GB of pixels, so memory stays small even for the HEALPix maps.
#
#   qsub postprocess/lightcone/finalise_job.sh
#   qsub -v TEST=1 postprocess/lightcone/finalise_job.sh

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

JID="${PBS_JOBID%%.*}"
ARGS=(); TAG="EOS26"; LOGDIR="$ROOT/logs"
if [[ "${TEST:-0}" == 1 ]]; then
  ARGS+=(--test); TAG="full_test_lightcone"; LOGDIR="$ROOT/logs/HII_DIM200_reference"
fi
PY=(uv run --no-sync --active --project "$ROOT")
"${PY[@]}" postprocess/lightcone/finalise_lightcones.py ${ARGS[@]+"${ARGS[@]}"} \
  --log-file "$LOGDIR/${TAG}_lightcone_finalise_${JID}.log"
