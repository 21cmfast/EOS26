#!/bin/bash
#PBS -N EOS26_fov_zoom
#PBS -q normal
#PBS -l ncpus=4
#PBS -l mem=48gb
#PBS -l walltime=4:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# The zoom movie of postprocess/plot_fov_zoom.py: it moves through the rect lightcone from z = 35 to the
# end of reionisation while zooming through the fields of view of 21-cm telescopes, with the galaxies of
# the galaxy properties job. Run where the lightcones and the PerturbedHaloCatalog files are.
#
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR postprocess/plot_fov_zoom_job.sh
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR,ARGS="--quantity neutral_fraction" postprocess/plot_fov_zoom_job.sh
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR,WHAT=stills postprocess/plot_fov_zoom_job.sh   # key frames first
#   qsub -v EOS26_TEMPLATE=EOS26_earlyEoR,ARGS="--geometry healpix --end 120" postprocess/plot_fov_zoom_job.sh
#
# Reading (estimate): rect ~19 GB of lightcone per quantity shown (one 43-slice block at a time, 0.4 GB
# each); healpix: the full-sky store while zoomed out (1.9 GB per 39-shell block) and 1 MiB tiles of the
# patch store; the galaxies once per node below --galaxies-zmax (coordinates of every halo, tens of GB
# at low z), then kept in plots/<movie>_galaxies/ for later runs. Rendering ~0.35 s (rect) to ~0.6 s
# (healpix) per 1080p frame, ~1650 frames. Memory: a few GB (healpix ~8 GB). Needs ffmpeg (module or
# `pip install imageio-ffmpeg` in the venv).
# Env: EOS26_TEMPLATE (EOS26), WHAT (movie | stills | figure), ARGS (more options), EOS26_VERSION
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
WHAT="${WHAT:-movie}"
LOG_DIR="$ROOT/logs"; [[ "$RUN" != EOS26 ]] && LOG_DIR="$ROOT/logs/$RUN"
mkdir -p "$LOG_DIR" "$ROOT/plots"
PY=(uv run --no-sync --active --project "$ROOT")
# shellcheck disable=SC2086  # ARGS is a list of options
EOS26_TEMPLATE="$RUN" "${PY[@]}" postprocess/plot_fov_zoom.py "$WHAT" --production --halos auto \
    --log-file "$LOG_DIR/${RUN}_fov_zoom_${WHAT}_${PBS_JOBID%%.*}.log" ${ARGS:-}
