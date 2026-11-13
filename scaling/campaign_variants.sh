#!/bin/bash
# Photon conservation and resolution benchmarks at 200-300 Mpc (scaling/bench_variant.py).
#
#   bash scaling/campaign_variants.sh --dry-run
#   bash scaling/campaign_variants.sh
#   python3 scaling/summarize_variants.py
#
# Two upstream sets (ICs, PFs, halo catalogues), each computed once by its baseline job;
# the photon-conservation variants of the same resolution reuse it (afterok):
#
#   cell 1.5 Mpc, HII_DIM 200 (300 Mpc):  no-photoncons | alpha-photoncons | f-photoncons
#   cell 1.0 Mpc, HII_DIM 300 (300 Mpc):  no-photoncons | alpha-photoncons | f-photoncons
#   cell 1.5 Mpc, HII_DIM 300 (450 Mpc):  no-photoncons   (same HII_DIM as the 1.0 Mpc runs)
#
# So: photon conservation at fixed resolution, 1.0 vs 1.5 Mpc at fixed volume (300 Mpc)
# and at fixed HII_DIM (300). All on normal nodes, 16 threads (N_THREADS = 16, as the
# production run and the NT_16 scaling results). Roughly 1-1.5k SU in total.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DRY=0; [[ "${1:-}" == --dry-run ]] && DRY=1
T=scaling/templates

submit() {  # submit <name> <resources> <env> [dependency, e.g. afterok:<id>] -> job id
  local cmd=(qsub -N "$1" -l "$2" -v "$3")
  [[ -n "${4:-}" ]] && cmd+=(-W "depend=$4")
  cmd+=(scaling/bench_variant_job.sh)
  if (( DRY )); then echo "${cmd[*]}" >&2; echo "JOB_$1"; else "${cmd[@]}"; fi
}

R200="ncpus=16,mem=64gb,walltime=06:00:00"
R300="ncpus=16,mem=64gb,walltime=10:00:00"

# The photon-conservation variants need the calibration fixes of bench_variant.py and an
# E-INTEGRAL calibration (21cmFAST 4.3.1 cannot calibrate Lagrangian source models,
# bug_reports/6_v4.3.1_photoncons_discrete_halos.md). The calibration writes nothing to the
# cache, so alpha and f can run side by side on the shared upstream boxes.
PC="EXTRA_ARGS=--pc-calibration-source-model+E-INTEGRAL"
a=$(submit v15_N200 "$R200" "TEMPLATE=$T/EOS26_v4.3.toml,HII_DIM=200")
submit v15_N200_pca "$R200" "TEMPLATE=$T/EOS26_v4.3_pc_alpha.toml,HII_DIM=200,PHASES=coeval,$PC" "afterok:$a"
submit v15_N200_pcf "$R200" "TEMPLATE=$T/EOS26_v4.3_pc_f.toml,HII_DIM=200,PHASES=coeval,$PC" "afterok:$a"

b=$(submit v10_N300 "$R300" "TEMPLATE=$T/EOS26_v4.3_cell1.0.toml,HII_DIM=300")
submit v10_N300_pca "$R300" "TEMPLATE=$T/EOS26_v4.3_cell1.0_pc_alpha.toml,HII_DIM=300,PHASES=coeval,$PC" "afterok:$b"
submit v10_N300_pcf "$R300" "TEMPLATE=$T/EOS26_v4.3_cell1.0_pc_f.toml,HII_DIM=300,PHASES=coeval,$PC" "afterok:$b"

submit v15_N300 "$R300" "TEMPLATE=$T/EOS26_v4.3.toml,HII_DIM=300"
