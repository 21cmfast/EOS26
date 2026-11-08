#!/bin/bash
# Submit one lightcone job per quantity, then the finalise job (postprocess/lightcone/README.md).
# Run from anywhere; the jobs run in the repository root.
#
#   postprocess/lightcone/submit_lightcones.sh                         # default quantities, rect + ring
#   postprocess/lightcone/submit_lightcones.sh density neutral_fraction
#   HEALPIX=1 postprocess/lightcone/submit_lightcones.sh               # + full-sky maps, one job each
#   GEOMETRY=healpix NSIDE=4096 postprocess/lightcone/submit_lightcones.sh density   # HEALPix only
#   AFTER=<jobid> postprocess/lightcone/submit_lightcones.sh           # start when that job ends (afterany)
#   PARTIAL=1 postprocess/lightcone/submit_lightcones.sh               # fill what is cached now (coevals running)
#   TEST=1 postprocess/lightcone/submit_lightcones.sh                  # the HII_DIM=200 reference
#   DRY_RUN=1 postprocess/lightcone/submit_lightcones.sh               # print the qsub commands only
#
# brightness_temp brings tau_21 and los_velocity along (the dv/dr correction needs them).
# Rect + ring jobs are limited by reading (~25 s per 13.5 GB box, ~40 min per quantity at
# HII_DIM=1500) and run on a part of a normal node; HEALPix jobs sample ~4e8 points per shell
# and take a whole node. Jobs are resumable: resubmit the same command after a failure.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DEFAULT_QUANTITIES="density brightness_temp spin_temperature neutral_fraction kinetic_temp_neutral J_21_LW sfrd_acg cumulative_recombinations"
if (( $# )); then QUANTITIES=("$@"); else read -ra QUANTITIES <<< "$DEFAULT_QUANTITIES"; fi
if [[ " ${QUANTITIES[*]} " == *" brightness_temp "* ]]; then
  for extra in tau_21 los_velocity; do
    [[ " ${QUANTITIES[*]} " == *" $extra "* ]] || QUANTITIES+=("$extra")
  done
fi

GEOMETRY="${GEOMETRY:-rect ring}"
TEST="${TEST:-0}"
if [[ "$TEST" == 1 ]]; then NSIDE="${NSIDE:-256}"; else NSIDE="${NSIDE:-2048}"; fi
OVERSAMPLE="${OVERSAMPLE:-1}"
DEP=(); [[ -n "${AFTER:-}" ]] && DEP=(-W "depend=afterany:${AFTER}")

submit() {  # submit <resources> <env> -> prints the job id
  local res=$1 env=$2
  local cmd=(qsub -N "$JOBNAME" -l "$res" ${DEP[@]+"${DEP[@]}"} -v "$env" postprocess/lightcone/lightcone_job.sh)
  if [[ "${DRY_RUN:-0}" == 1 ]]; then echo "${cmd[*]}" >&2; echo "DRYRUN"; else "${cmd[@]}"; fi
}

resources() {  # resources <geometry> <quantity>
  local geom=$1 q=$2
  if [[ "$TEST" == 1 ]]; then echo "ncpus=4,mem=16gb,walltime=01:00:00"; return; fi
  if [[ "$geom" == *healpix* ]]; then
    if [[ "$q" == los_velocity ]]; then echo "ncpus=48,mem=190gb,walltime=36:00:00"
    else echo "ncpus=48,mem=190gb,walltime=12:00:00"; fi
  else
    # los_velocity on the ring needs all three velocities at two redshifts (81 GB at 1500^3)
    if [[ "$q" == los_velocity && "$geom" == *ring* ]]; then echo "ncpus=28,mem=120gb,walltime=08:00:00"
    else echo "ncpus=12,mem=48gb,walltime=04:00:00"; fi
  fi
}

# rect/ring in one job per quantity; healpix in its own job per quantity
JOB_SETS=()
LIGHT="$(echo "$GEOMETRY" | tr ' ' '\n' | { grep -v '^healpix$' || true; } | tr '\n' ' ' | sed 's/ *$//')"
[[ -n "$LIGHT" ]] && JOB_SETS+=("$LIGHT")
if [[ " $GEOMETRY " == *" healpix "* || "${HEALPIX:-0}" == 1 ]]; then JOB_SETS+=("healpix"); fi

IDS=()
for q in "${QUANTITIES[@]}"; do
  for g in "${JOB_SETS[@]}"; do
    JOBNAME="lc_${q:0:12}"
    env="QUANTITY=$q,GEOMETRY=${g// /+},TEST=$TEST,NSIDE=$NSIDE,OVERSAMPLE=$OVERSAMPLE,PARTIAL=${PARTIAL:-0}"  # + for spaces
    id=$(submit "$(resources "$g" "$q")" "$env")
    echo "$q [$g]: $id"
    IDS+=("$id")
  done
done

if [[ "${DRY_RUN:-0}" == 1 ]]; then
  echo "qsub -W depend=afterok:<all of the above> -v TEST=$TEST postprocess/lightcone/finalise_job.sh" >&2
  exit 0
fi
dep=$(IFS=:; echo "${IDS[*]}")
fid=$(qsub -W "depend=afterok:$dep" -v "TEST=$TEST" postprocess/lightcone/finalise_job.sh)
echo "finalise: $fid (after all of them succeed; resubmit it by hand otherwise)"
