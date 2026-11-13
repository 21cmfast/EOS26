#!/bin/bash
#PBS -N EOS26_variant
#PBS -q normal
#PBS -l ncpus=16
#PBS -l mem=64gb
#PBS -l walltime=08:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# One benchmark variant (scaling/bench_variant.py): photon conservation and/or 1.0 Mpc cells.
# Normally submitted by scaling/campaign_variants.sh. By hand:
#
#   qsub -v TEMPLATE=scaling/templates/EOS26_v4.3_pc_alpha.toml,HII_DIM=200 scaling/bench_variant_job.sh
#   qsub -v TEMPLATE=...,HII_DIM=200,PHASES=coeval scaling/bench_variant_job.sh   # upstream cached
#
# Env: TEMPLATE, HII_DIM (required); PHASES (all); EXTRA_ARGS (more bench_variant.py flags,
#      joined by +, e.g. --pc-calibration-source-model+E-INTEGRAL); EOS26_VERSION (v4.3).
# N_THREADS = ncpus (16 by default, as production and the NT_16 scaling results).
# Results: scaling/results/variants/<template name>_N<HII_DIM>.{json,log}

export PATH="$HOME/.local/bin:$PATH"
cd "$PBS_O_WORKDIR"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

EOS26_VERSION="${EOS26_VERSION:-v4.3}"
source "$ROOT/envs/use.sh" "$EOS26_VERSION"
set -euo pipefail

: "${TEMPLATE:?set TEMPLATE}" "${HII_DIM:?set HII_DIM}"
THREADS="${PBS_NCPUS:-16}"
export OMP_NUM_THREADS="$THREADS" OMP_DYNAMIC=FALSE
unset OMP_PROC_BIND OMP_PLACES

extra=()
if [[ -n "${EXTRA_ARGS:-}" ]]; then IFS='+' read -r -a extra <<< "$EXTRA_ARGS"; fi
PY=(uv run --no-sync --active --project "$ROOT")
"${PY[@]}" scaling/bench_variant.py --template "$TEMPLATE" --hii-dim "$HII_DIM" \
  --n-threads "$THREADS" --phases "${PHASES:-all}" ${extra[@]+"${extra[@]}"}
