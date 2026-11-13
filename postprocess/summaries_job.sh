#!/bin/bash
#PBS -N EOS26_summaries
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=64gb
#PBS -l walltime=2:00:00
#PBS -l storage=scratch/qp00+gdata/qp00

# Run postprocess/plot_all_summaries.ipynb without Jupyter (postprocess/run_notebook.py).
# Plots go to plots/summaries/; the printed tables (x_HI levels, tau_e, UV LF deviations)
# go to logs/summaries_<jobid>.log. With TEST = True (the notebook's setting) it reads the
# HII_DIM=200 test cache, so start it after the test job.
# 16 cpus: convert_halo_properties runs with the template's N_THREADS (16).
#
# Usage: qsub -W depend=afterok:<full_test_job id> postprocess/summaries_job.sh
#        qsub postprocess/summaries_job.sh
#        qsub -v SET="TEST=True" postprocess/summaries_job.sh   # --set NAME=VALUE for run_notebook.py
#        qsub -v NOTEBOOK=postprocess/EOS26_smallbox_xHI.ipynb postprocess/summaries_job.sh

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

# 21cmFAST environment: venv + modules (envs/use.sh; venv paths in scaling/config.sh).
EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

JID="${PBS_JOBID%%.*}"
NOTEBOOK="${NOTEBOOK:-postprocess/plot_all_summaries.ipynb}"
SET_ARGS=()
for kv in ${SET:-}; do SET_ARGS+=(--set "$kv"); done
mkdir -p logs
uv run --no-sync --active --project "$ROOT" postprocess/run_notebook.py "$NOTEBOOK" \
    ${SET_ARGS[@]+"${SET_ARGS[@]}"} 2>&1 | tee "logs/summaries_${JID}.log"
