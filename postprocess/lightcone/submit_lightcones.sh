#!/bin/bash
# Submit one lightcone job per quantity and geometry set, then the finalise job
# (postprocess/lightcone/README.md). Run from anywhere; the jobs run in the repository root.
#
# The geometries and choices (decision list of 17 Nov 2026) are in eos_lightcones.py:
# rect, angular plane, full sky (Nside 1024) and a 45 deg patch (Nside 4096) around (0, 0),
# no frame rotation, RSDs on, z = 5.01-35. RSDS=0|1, ROTATION='SEQ:a,b,c'|none and
# PATCH_CENTER='LON LAT' override them (all jobs of one run must use the same values).
#
#   postprocess/lightcone/submit_lightcones.sh                         # default quantities, all geometries
#   postprocess/lightcone/submit_lightcones.sh density neutral_fraction
#   GEOMETRY="rect angular_plane" postprocess/lightcone/submit_lightcones.sh   # only some geometries
#   EOS26_TEMPLATE=EOS26_earlyEoR postprocess/lightcone/submit_lightcones.sh   # the other run
#   AFTER=<jobid> postprocess/lightcone/submit_lightcones.sh           # start when that job ends (afterany)
#   PARTIAL=1 postprocess/lightcone/submit_lightcones.sh               # fill what is cached now (coevals running)
#   TEST=1 postprocess/lightcone/submit_lightcones.sh                  # the HII_DIM=200 test (smaller HEALPix)
#   DRY_RUN=1 postprocess/lightcone/submit_lightcones.sh               # print the qsub commands only
#
# brightness_temp brings tau_21 and los_velocity along (dv/dr and RSDs need them).
# Jobs per quantity: rect + angular plane together (limited by reading, ~25 s per 13.5 GB
# box at HII_DIM=1500); the full sky and the patch each on a whole node (48 threads, each
# filling a part of the map). Jobs are resumable: resubmit the same command after a
# failure. The finalise job starts when all of them have succeeded.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# as eos_lightcones.DEFAULT_QUANTITIES (the released ones; [CII] later)
DEFAULT_QUANTITIES="density brightness_temp spin_temperature neutral_fraction kinetic_temp_neutral J_21_LW sfrd_acg cumulative_recombinations los_velocity ionisation_rate_G12 sfrd_mcg n_ion xray_emissivity"
if (( $# )); then QUANTITIES=("$@"); else read -ra QUANTITIES <<< "$DEFAULT_QUANTITIES"; fi
if [[ " ${QUANTITIES[*]} " == *" brightness_temp "* ]]; then
  for extra in tau_21 los_velocity; do
    [[ " ${QUANTITIES[*]} " == *" $extra "* ]] || QUANTITIES+=("$extra")
  done
fi

GEOMETRY="${GEOMETRY:-rect angular_plane healpix patch}"
if [[ -n "${RSDS:-}" && "$RSDS" != 0 && "$RSDS" != 1 ]]; then echo "RSDS must be 0 or 1" >&2; exit 1; fi
RUN="${EOS26_TEMPLATE:-EOS26}"
TEST="${TEST:-0}"
# the HEALPix cost depends on the number of pixels, not on the box: smaller maps for the test
if [[ "$TEST" == 1 ]]; then
  HEALPIX_NSIDE="${HEALPIX_NSIDE:-256}"; PATCH_NSIDE="${PATCH_NSIDE:-1024}"
fi
DEP=(); [[ -n "${AFTER:-}" ]] && DEP=(-W "depend=afterany:${AFTER}")
PASS="EOS26_TEMPLATE=$RUN,TEST=$TEST,PARTIAL=${PARTIAL:-0}"
for v in RSDS ZMIN ZMAX HEALPIX_NSIDE PATCH_NSIDE EOS26_LIGHTCONE_DIR; do
  [[ -n "${!v:-}" ]] && PASS+=",$v=${!v}"
done
# qsub -v cannot carry commas or spaces inside a value: + instead (lightcone_job.sh undoes it)
[[ -n "${ROTATION:-}" ]] && PASS+=",ROTATION=${ROTATION//,/+}"
if [[ -n "${PATCH_CENTER:-}" ]]; then PC="${PATCH_CENTER# }"; PASS+=",PATCH_CENTER=${PC// /+}"; fi

submit() {  # submit <resources> <env> -> prints the job id
  local res=$1 env=$2
  local cmd=(qsub -P qp00 -N "$JOBNAME" -l "$res" ${DEP[@]+"${DEP[@]}"} -v "$env" postprocess/lightcone/lightcone_job.sh)
  if [[ "${DRY_RUN:-0}" == 1 ]]; then echo "${cmd[*]}" >&2; echo "DRYRUN"; else "${cmd[@]}"; fi
}

resources() {  # resources <job set> <quantity>
  local set=$1 q=$2 vel=0
  [[ "$q" == los_velocity ]] && vel=1   # three velocity boxes per node redshift
  if [[ "$TEST" == 1 ]]; then
    case "$set" in
      healpix|patch) echo "ncpus=16,mem=64gb,walltime=02:00:00" ;;
      *) echo "ncpus=4,mem=16gb,walltime=01:00:00" ;;
    esac
    return
  fi
  # memory: 13.5 GB boxes at 2 (one thread) or 3 (several threads) node redshifts.
  # Sampling per quantity: full sky 201 M samples per slice (65-89 core-h), the 45 deg
  # patch 118 M (~52 core-h); los_velocity 3x. Not measured on 48 threads yet.
  case "$set:$vel" in
    healpix:0) echo "ncpus=48,mem=190gb,walltime=12:00:00" ;;
    healpix:1) echo "ncpus=48,mem=190gb,walltime=36:00:00" ;;
    patch:0)   echo "ncpus=48,mem=190gb,walltime=08:00:00" ;;
    patch:1)   echo "ncpus=48,mem=190gb,walltime=24:00:00" ;;
    *:0)       echo "ncpus=12,mem=48gb,walltime=04:00:00" ;;
    *:1)       echo "ncpus=28,mem=110gb,walltime=08:00:00" ;;
  esac
}

# rect and angular plane in one job per quantity; healpix and patch each in their own job
JOB_SETS=()
LIGHT="$(echo "$GEOMETRY" | tr ' ' '\n' | { grep -Ev '^(healpix|patch)$' || true; } | tr '\n' ' ' | sed 's/ *$//')"
[[ -n "$LIGHT" ]] && JOB_SETS+=("$LIGHT")
[[ " $GEOMETRY " == *" healpix "* ]] && JOB_SETS+=("healpix")
[[ " $GEOMETRY " == *" patch "* ]] && JOB_SETS+=("patch")

IDS=()
for q in "${QUANTITIES[@]}"; do
  for g in "${JOB_SETS[@]}"; do
    JOBNAME="lc_${q:0:12}"
    id=$(submit "$(resources "$g" "$q")" "QUANTITY=$q,GEOMETRY=${g// /+},$PASS")  # + for spaces
    echo "$RUN $q [$g]: $id"
    IDS+=("$id")
  done
done

FPASS="EOS26_TEMPLATE=$RUN,TEST=$TEST"
for v in RSDS ZMIN ZMAX HEALPIX_NSIDE DEGRADE_NSIDE EOS26_LIGHTCONE_DIR; do
  [[ -n "${!v:-}" ]] && FPASS+=",$v=${!v}"
done
if [[ "${DRY_RUN:-0}" == 1 ]]; then
  echo "qsub -P qp00 -W depend=afterok:<all of the above> -v $FPASS postprocess/lightcone/finalise_job.sh" >&2
  exit 0
fi
dep=$(IFS=:; echo "${IDS[*]}")
fid=$(qsub -P qp00 -W "depend=afterok:$dep" -v "$FPASS" postprocess/lightcone/finalise_job.sh)
echo "finalise: $fid (after all of them succeed; resubmit it by hand otherwise)"
