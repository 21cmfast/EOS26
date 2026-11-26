#!/bin/bash
#PBS -N EOS26_box_movie
#PBS -q normal
#PBS -l ncpus=48
#PBS -l mem=32gb
#PBS -l walltime=1:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# The rotating-cube movie of postprocess/box_movie.py (after visio's EOS movie): T_b from z = 35 to 5,
# the whole box block-averaged to 500^3, zooming into a 750 cMpc sub-cube at the native cells.
# First reduce the coevals (one node, ~40 min of reading 92 x 13.5 GB; writes ~46 GB to
# plots/movie/data/), then render (~0.3 s per 800 px frame on 48 cores, ~750 frames):
#
#   qsub -l ncpus=1,mem=16gb,walltime=3:00:00 -v EOS26_TEMPLATE=EOS26_earlyEoR,WHAT=prepare postprocess/box_movie_job.sh
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR,WHAT=stills postprocess/box_movie_job.sh     # a few frames as PNG
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR postprocess/box_movie_job.sh                 # the movie
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR,ARGS="--gif --zoom-z 12 10" postprocess/box_movie_job.sh
#
# prepare resumes where it stopped and skips nodes whose coevals are not there yet (rerun it later).
# The movie and stills go to plots/movie/outputs/ (plots/movie/ is not in git). Needs numba in the venv
# and ffmpeg (module or `pip install imageio-ffmpeg`).
# Env: EOS26_TEMPLATE (EOS26), WHAT (render | stills | prepare), ARGS (more options), EOS26_VERSION
#      (v4.3_post).

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

EOS26_VERSION="${EOS26_VERSION:-v4.3_post}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail
module load ffmpeg 2>/dev/null || true

RUN="${EOS26_TEMPLATE:-EOS26}"
WHAT="${WHAT:-render}"
LOG_DIR="$ROOT/logs"; [[ "$RUN" != EOS26 ]] && LOG_DIR="$ROOT/logs/$RUN"
mkdir -p "$LOG_DIR"
export NUMBA_NUM_THREADS="${PBS_NCPUS:-1}"
PY=(uv run --no-sync --active --project "$ROOT")
# shellcheck disable=SC2086  # ARGS is a list of options
EOS26_TEMPLATE="$RUN" "${PY[@]}" postprocess/box_movie.py "$WHAT" ${ARGS:-} \
    > "$LOG_DIR/${RUN}_box_movie_${WHAT}_${PBS_JOBID%%.*}.log" 2>&1
