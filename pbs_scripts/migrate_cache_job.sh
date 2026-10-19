#!/bin/bash
#PBS -N EOS26_migrate
#PBS -q hugemem
#PBS -l ncpus=12
#PBS -l mem=500GB
#PBS -l walltime=24:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -P qp00

# Convert the ICs, PFs and halo catalogs of the production cache written by
# 21cmFAST 4.2 to 4.3, so that 4.3 can find them (its cache hashes differ). The
# converted files are written next to the originals; the originals are kept.
# Coevals are not converted: their physics changed in 4.3, so they are recomputed.
# Memory: one array at a time (the largest is a high-res IC field, ~360 GB at
# HII_DIM=1500). Re-submitting is safe: files already converted are skipped.
#
#   qsub -v DRY_RUN=1 pbs_scripts/migrate_cache_job.sh   # report only
#   qsub pbs_scripts/migrate_cache_job.sh

export PATH="$HOME/.local/bin:$PATH"
set -euo pipefail
ROOT="$(cd "$PBS_O_WORKDIR" && pwd)"
cd "$ROOT"

source "$ROOT/envs/use.sh" v4.3
set -euo pipefail
module list

CACHE=$(python -W ignore -c 'import sys; sys.path.insert(0, "run_scripts"); import settings; print(settings.CACHE_FULL)')
JID="${PBS_JOBID%%.*}"
mkdir -p logs
extra=()
if [[ -n "${DRY_RUN:-}" ]]; then extra+=(--dry-run); fi
echo "migrating $CACHE (kinds: InitialConditions PerturbedField HaloCatalog) ${extra[*]:-}"
21cmfast migrate "$CACHE" --kind InitialConditions PerturbedField HaloCatalog "${extra[@]}" \
    2>&1 | tee "logs/EOS26_migrate_${JID}.log"
