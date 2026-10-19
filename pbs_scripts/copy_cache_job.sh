#!/bin/bash
#PBS -N EOS26_copy
#PBS -q copyq
#PBS -P qp00
#PBS -l ncpus=1,mem=4GB,walltime=10:00:00
#PBS -l storage=scratch/qp00+gdata/qp00
#PBS -j oe

# ONE round (< 10 h, the copyq limit) of copying the production cache from
# scratch to gdata. Each round continues where the previous one stopped, so
# submit as many rounds as needed -- pbs_scripts/submit_copy_and_migrate.sh
# chains them and the migration. When the copy is verified complete, the round
# writes $DONE; later rounds then do nothing, and migrate_cache_job.sh refuses
# to run without it.
#
# Progress (from a login node):  tail -f /g/data/qp00/$USER/rsync_EOS26_cache.log

set -uo pipefail
cd "${PBS_O_WORKDIR:-$PWD}"
DATA="${EOS26_DATA:-/g/data/qp00/$USER}"        # = DATA_ROOT in run_scripts/settings.py
SRC="${COPY_SRC:-$PWD/EOS26_cache}/"
DST="$DATA/EOS26_cache/"
LOG="$DATA/rsync_EOS26_cache.log"
DONE="$DATA/EOS26_cache.copy_complete"
# Stop rsync cleanly (it removes its temporary file on SIGTERM) before PBS kills the job.
RSYNC_TIME="${RSYNC_TIME:-570m}"   # 9.5 h; GNU timeout takes one unit only

if [[ -e "$DONE" ]]; then
  echo "copy already complete ($DONE: $(cat "$DONE")); nothing to do"
  exit 0
fi
[[ -d "$SRC" ]] || { echo "ERROR: source $SRC not found" >&2; exit 1; }
mkdir -p "$DST"

echo "=== $(date -u +%FT%TZ) copy round ${PBS_JOBID:-local} on $(hostname): $SRC -> $DST" | tee -a "$LOG"
timeout --signal=TERM "$RSYNC_TIME" \
  rsync -a --size-only --no-inc-recursive --info=progress2 "$SRC" "$DST" >> "$LOG" 2>&1
status=$?
echo "=== $(date -u +%FT%TZ) rsync exit status $status$( ((status == 124)) && echo ' (time limit of this round: the next round continues)')" | tee -a "$LOG"

if (( status == 0 )); then
  # Verify: nothing left to transfer, and the same number of files on both sides.
  left=$(rsync -a --size-only --dry-run --out-format='%n' "$SRC" "$DST" | grep -cv '/$')
  n_src=$(find "$SRC" -type f ! -name '.*' | wc -l)
  n_dst=$(find "$DST" -type f ! -name '.*' | wc -l)
  echo "files: scratch $n_src, gdata $n_dst, still to copy $left" | tee -a "$LOG"
  if (( left == 0 && n_src == n_dst )); then
    echo "$(date -u +%FT%TZ) $n_dst files" > "$DONE"
    echo "copy COMPLETE and verified -> $DONE" | tee -a "$LOG"
    exit 0
  fi
  echo "copy not verified yet; the next round continues" | tee -a "$LOG"
fi
exit "$status"
