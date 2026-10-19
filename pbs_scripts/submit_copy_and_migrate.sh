#!/bin/bash
# Copy the production cache from scratch to gdata and then convert it for
# 21cmFAST 4.3, without waiting in between:
#   * N copy rounds on copyq (pbs_scripts/copy_cache_job.sh, < 10 h each), each
#     starting when the previous one ends; rounds after the copy is complete exit
#     at once;
#   * then the migration on hugemem (pbs_scripts/migrate_cache_job.sh), which only
#     runs if the copy was verified complete.
#
#   bash pbs_scripts/submit_copy_and_migrate.sh                    # 3 copy rounds
#   bash pbs_scripts/submit_copy_and_migrate.sh --after 123456     # wait for a running copy job first
#   bash pbs_scripts/submit_copy_and_migrate.sh --rounds 2 --dry-run-migrate
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

rounds=3 after="" migrate_vars=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --rounds) rounds=$2; shift 2 ;;
    --after) after=$2; shift 2 ;;
    --dry-run-migrate) migrate_vars="DRY_RUN=1"; shift ;;
    -h|--help) sed -n '2,/^set /p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 1 ;;
  esac
done

prev=$after
for i in $(seq 1 "$rounds"); do
  dep=()
  [[ -n "$prev" ]] && dep=(-W "depend=afterany:$prev")
  prev=$(qsub "${dep[@]}" -N "EOS26_copy$i" pbs_scripts/copy_cache_job.sh)
  echo "copy round $i:  $prev${dep[*]:+  (after ${dep[1]#depend=afterany:})}"
done
mig=$(qsub -W "depend=afterany:$prev" ${migrate_vars:+-v "$migrate_vars"} pbs_scripts/migrate_cache_job.sh)
echo "migration:     $mig  (after $prev; runs only if the copy is complete${migrate_vars:+; dry run})"
echo "progress: tail -f /g/data/qp00/$USER/rsync_EOS26_cache.log ; qstat -u $USER"
