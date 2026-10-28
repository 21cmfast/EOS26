#!/bin/bash
#PBS -N EOS26_plots
#PBS -q normal
#PBS -l ncpus=4
#PBS -l mem=32gb
#PBS -l walltime=2:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Plots of the production run, straight from its cache (postprocess/eos_boxes.py reads
# one plane per box, so memory stays small at HII_DIM=1500):
#   * plots/ICs_EOS26*.png          slices of the initial conditions
#   * plots/PF_EOS26_z*.png         slices of the perturbed density at a few redshifts
#   * plots/lightcones_EOS26_v*.png lightcones of $QUANTITIES, as far as they are computed
# Resubmit it whenever you want the lightcones updated: redshifts the coeval jobs have
# done since are added, and only new boxes are read (the planes are kept in
# <cache>/lightcone_planes/). The first run reads every halo catalogue once (several
# hundred GB at HII_DIM=1500), so it takes longest.
#
# Usage: qsub postprocess/plots_job.sh
#        qsub -W depend=afterany:<coeval job id> postprocess/plots_job.sh   # after a coeval job
#        qsub -v QUANTITIES="density stellar_mass sfr" postprocess/plots_job.sh
#        qsub -v LIGHTCONE_ONLY=1 postprocess/plots_job.sh
#        qsub -v TEST=1 postprocess/plots_job.sh                          # the HII_DIM=200 reference

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

# 21cmFAST environment: venv + modules (envs/use.sh; venv paths in scaling/config.sh).
EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

QUANTITIES="${QUANTITIES:-density stellar_mass brightness_temp spin_temperature neutral_fraction}"
TEST_ARG=(); [[ "${TEST:-0}" == 1 ]] && TEST_ARG=(--test)
PY=(uv run --no-sync --active --project "$ROOT")

if [[ "${LIGHTCONE_ONLY:-0}" != 1 ]]; then
  "${PY[@]}" postprocess/plot_ics.py ${TEST_ARG[@]+"${TEST_ARG[@]}"}
  "${PY[@]}" postprocess/plot_ics.py ${TEST_ARG[@]+"${TEST_ARG[@]}"} --zoom --vel
  "${PY[@]}" postprocess/plot_pf.py ${TEST_ARG[@]+"${TEST_ARG[@]}"} --redshift 5 8 10 15 20 30
  "${PY[@]}" postprocess/plot_pf.py ${TEST_ARG[@]+"${TEST_ARG[@]}"} --redshift 10 --zoom --vel
fi
# shellcheck disable=SC2086  # QUANTITIES is a list
"${PY[@]}" postprocess/plot_lightcone.py ${TEST_ARG[@]+"${TEST_ARG[@]}"} --quantities $QUANTITIES
