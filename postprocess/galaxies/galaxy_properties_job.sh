#!/bin/bash
#PBS -N EOS26_galaxies
#PBS -q hugemem
#PBS -l ncpus=16
#PBS -l mem=400gb
#PBS -l walltime=12:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# Galaxy properties (Eulerian positions, halo and stellar masses, SFRs, ...) of every halo at
# every node redshift, written into the run's cache as PerturbedHaloCatalog files, for the
# line-intensity maps and the galaxy catalogue (postprocess/galaxies/README.md). Needs the
# coevals of the run (the TsBox and IonizedBox of every node redshift).
#
#   qsub postprocess/galaxies/galaxy_properties_job.sh                                   # EOS26
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR postprocess/galaxies/galaxy_properties_job.sh
#   qsub -v TEST=1 -q normal -l ncpus=4,mem=16gb,walltime=01:00:00 \
#        postprocess/galaxies/galaxy_properties_job.sh                                   # HII_DIM=200 test
#   qsub -v ZMIN=5,ZMAX=8 postprocess/galaxies/galaxy_properties_job.sh                  # some node redshifts
#
# Resubmit the same job to resume: complete node redshifts are skipped.
# Memory (estimate at z = 5, not measured): IC velocities and v_cb 95 GB (read once), the
# previous TsBox and IonizedBox 40 GB, turnover-mass grids 27 GB, 1.7e9 halos 47 GB in and
# 73 GB out: ~290 GB. Time (estimate): a few minutes per node redshift at low z (mostly
# reading and writing), a few hours in all. Output ~1 TB per run on gdata.
# Env: EOS26_TEMPLATE (EOS26; the run), TEST (0), ZMIN, ZMAX, CLOBBER (0; 1 = compute
#      complete node redshifts again), EOS26_VERSION (v4.3_post: 21cmFAST >= 4.3.2),
#      EOS26_RUN_THREADS (default: ncpus; does not change the result).

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
# N_THREADS = 16 is in the cache hash: the threads are changed at run time only
# (run_scripts/sim_steps.py), as for the coevals
RUN_THREADS="${EOS26_RUN_THREADS:-${PBS_NCPUS:-16}}"
export EOS26_RUN_THREADS="$RUN_THREADS" OMP_NUM_THREADS="$RUN_THREADS" OMP_DYNAMIC=FALSE
unset OMP_PROC_BIND OMP_PLACES

ARGS=()
[[ -n "${ZMIN:-}" ]] && ARGS+=(--zmin "$ZMIN")
[[ -n "${ZMAX:-}" ]] && ARGS+=(--zmax "$ZMAX")
[[ "${CLOBBER:-0}" == 1 ]] && ARGS+=(--clobber)
LOGDIR="$ROOT/logs"; [[ "$RUN" != EOS26 ]] && LOGDIR="$ROOT/logs/$RUN"
TAG="${RUN}_galaxies"
if [[ "${TEST:-0}" == 1 ]]; then
  ARGS+=(--test); TAG="${RUN}_test_galaxies"; LOGDIR="$ROOT/logs/HII_DIM200_reference"
fi
mkdir -p "$LOGDIR"

uv run --no-sync --active --project "$ROOT" postprocess/galaxies/galaxy_properties.py \
    ${ARGS[@]+"${ARGS[@]}"} --log-file "$LOGDIR/${TAG}_${JID}.log"
