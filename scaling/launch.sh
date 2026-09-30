#!/bin/bash
# Submit one PBS job per scaling configuration (HII_DIM x N_THREADS).
#
#   bash scaling/launch.sh --version v4.2 --dims "100 200 300" --threads "16 48"
#   bash scaling/launch.sh --version v4.3 --pairs "200:1 200:4 400:32"
#
# Jobs are independent and run in parallel; each writes its own results
# folder scaling/results/<version>/HII_DIM_XXXX_NT_YY/ as it goes.
#
# The launcher is idempotent -- just run it again at any time:
#   * complete configurations are skipped,
#   * configurations whose job is still queued/running are skipped,
#   * incomplete ones are (re)submitted and RESUME from the beginning of the
#     first unfinished phase (completed phases are not re-measured).
#
# Options
#   --version V         21cmFAST version label (v4.2 | v4.3)            [required]
#   --dims "D ..."      HII_DIM values        } cross product,
#   --threads "N ..."   N_THREADS values      } and/or
#   --pairs "D:N ..."   explicit HII_DIM:N_THREADS pairs
#   --phases LIST       phases to measure, e.g. ics,pf (default: all)
#   --coeval-batch N    measure coevals like production batch jobs: a fresh
#                       process per N redshifts (results in ..._CBNN/). Default 0:
#                       the full evolution in one process
#   --keep-sim          keep the simulation cache when a configuration completes
#   --restart           archive previous results of these configurations, start over
#   --mem GB            override the memory request
#   --walltime H:M:S    override the walltime request
#   --queue Q           override the queue
#   --retry             resubmit even configurations that already failed
#                       SC_MAX_ATTEMPTS times (see config.sh)
#   --dry-run           print the qsub commands, submit nothing
#   --no-preflight      skip the login-node check of venv/template
#   -h | --help

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"
# shellcheck source=_lib.sh
source "$HERE/_lib.sh"

usage() { sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }
die() { echo "ERROR: $*" >&2; exit 1; }

VERSION="" DIMS="" THREADS="" PAIRS="" PHASES="all" CBATCH=0
KEEP_SIM=0 RESTART=0 DRY=0 PREFLIGHT=1 RETRY=0
MEM_OVERRIDE="" WALL_OVERRIDE="" QUEUE_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION=$2; shift 2 ;;
    --dims) DIMS=$2; shift 2 ;;
    --threads) THREADS=$2; shift 2 ;;
    --pairs) PAIRS=$2; shift 2 ;;
    --phases) PHASES=$2; shift 2 ;;
    --coeval-batch) CBATCH=$2; shift 2 ;;
    --keep-sim) KEEP_SIM=1; shift ;;
    --restart) RESTART=1; shift ;;
    --mem) MEM_OVERRIDE=$2; shift 2 ;;
    --walltime) WALL_OVERRIDE=$2; shift 2 ;;
    --queue) QUEUE_OVERRIDE=$2; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --retry) RETRY=1; shift ;;
    --no-preflight) PREFLIGHT=0; shift ;;
    -h|--help) usage 0 ;;
    *) die "unknown option '$1' (see --help)" ;;
  esac
done

[[ -n "$VERSION" ]] || die "--version is required"
VENV=$(sc_venv "$VERSION") || die "unknown version '$VERSION' (edit sc_venv in scaling/config.sh)"
TEMPLATE=$(sc_template "$VERSION")
EXPECT=$(sc_expect_version "$VERSION")
[[ -f "$(sc_abs "$ROOT" "$TEMPLATE")" ]] || die "template not found: $TEMPLATE"
[[ -z "$MEM_OVERRIDE" || "$MEM_OVERRIDE" =~ ^[0-9]+$ ]] || die "--mem takes an integer number of GB"
[[ -z "$WALL_OVERRIDE" || "$WALL_OVERRIDE" =~ ^[0-9]+:[0-5][0-9]:[0-5][0-9]$ ]] || die "--walltime takes HH:MM:SS"
[[ "$CBATCH" =~ ^[0-9]+$ ]] || die "--coeval-batch takes a non-negative integer"
PHASES_PBS=${PHASES//,/+}   # qsub -v splits on commas
[[ "$PHASES_PBS" =~ ^[a-z+]+$ ]] || die "bad --phases '$PHASES'"

# ---- configuration list (deduplicated, sorted) ------------------------------
declare -a CONFIGS=()
for d in $DIMS; do for n in $THREADS; do CONFIGS+=("$d:$n"); done; done
for p in $PAIRS; do CONFIGS+=("$p"); done
[[ ${#CONFIGS[@]} -gt 0 ]] || die "nothing to launch: give --dims and --threads, and/or --pairs"
mapfile -t CONFIGS < <(printf '%s\n' "${CONFIGS[@]}" | sort -t: -k1,1n -k2,2n -u)
for c in "${CONFIGS[@]}"; do
  [[ "$c" =~ ^[0-9]+:[0-9]+$ ]] || die "bad configuration '$c' (want HII_DIM:N_THREADS)"
  (( ${c#*:} >= 1 && ${c#*:} <= 48 )) || die "N_THREADS must be 1..48 on one Gadi node (got $c)"
done

# ---- preflight on the login node: right venv, template loads -----------------
if (( PREFLIGHT )); then
  [[ -x "$VENV/bin/python" ]] || die "venv python not found: $VENV/bin/python"
  echo "preflight: $VENV"
  ( sc_load_modules >/dev/null 2>&1 || true
    cd "$ROOT"
    "$VENV/bin/python" - "$TEMPLATE" "$EXPECT" "${CONFIGS[0]%%:*}" <<'PY'
import re, sys, warnings
warnings.simplefilter("ignore")
template, expect, dim = sys.argv[1], sys.argv[2], int(sys.argv[3])
sys.path.insert(0, "run_scripts")
import py21cmfast as p21c
import sim_steps  # noqa: F401  (must import with this version)
v = p21c.__version__
if not re.search(expect, v):
    sys.exit(f"py21cmfast {v} does not match expected /{expect}/ -- wrong venv? (scaling/config.sh)")
inp = p21c.InputParameters.from_template(template, HII_DIM=dim)
print(f"preflight OK: py21cmfast {v}; {template} loads (HII_DIM={dim}, BOX_LEN={inp.simulation_options.BOX_LEN:.0f} Mpc)")
PY
  ) || die "preflight failed"
fi

command -v qsub >/dev/null 2>&1 || (( DRY )) || die "qsub not found (use --dry-run off the cluster)"

RESULTS_ABS=$(sc_abs "$ROOT" "$SC_RESULTS_ROOT")
SIMS_ABS=$(sc_abs "$ROOT" "$SC_SIM_ROOT")
[[ "$RESULTS_ABS$SIMS_ABS" != *,* ]] || die "results/sim roots must not contain commas (qsub -v)"

EXTRA=()
(( KEEP_SIM )) && EXTRA+=("--keep-sim")
(( RESTART )) && EXTRA+=("--restart")
EXTRA_PBS=$(IFS=+; echo "${EXTRA[*]:-}")

printf '\n%-23s %-9s %-8s %-9s %-10s %s\n' "config" "queue" "mem" "walltime" "disk~" "action"
n_sub=0 n_skip=0 disk_total=0
for c in "${CONFIGS[@]}"; do
  dim=${c%%:*} nt=${c#*:}
  cdir=$(sc_config_dir "$ROOT" "$VERSION" "$dim" "$nt" "$CBATCH")
  name="$(sc_config_name "$dim" "$nt" "$CBATCH")"

  flags=$(sc_state_flags "$cdir")
  # Skip complete / active configurations.
  if (( ! RESTART )) && [[ " $flags " == *" complete "* ]]; then
    printf '%-23s %-40s %s\n' "$name" "" "skip (complete)"; n_skip=$((n_skip + 1)); continue
  fi
  last_jid=$(tail -n 1 "$cdir/pbs/jobids" 2>/dev/null | awk '{print $2}' || true)
  if sc_job_active "$last_jid"; then
    printf '%-23s %-40s %s\n' "$name" "" "skip (job $last_jid queued/running)"; n_skip=$((n_skip + 1)); continue
  fi

  if (( ! RESTART && ! RETRY )) && [[ " $flags " == *" retries "* ]]; then
    printf '%-23s %-40s %s\n' "$name" "" "skip (failed ${SC_MAX_ATTEMPTS}x: see $cdir/run.log; then --retry)"
    n_skip=$((n_skip + 1)); continue
  fi

  # Resources. Retries after a memory / walltime kill ask for 50% more,
  # based on the previous request of this configuration.
  prev=$(tail -n 1 "$cdir/pbs/jobids" 2>/dev/null || true)
  prev_mem=$(sed -n 's/.* mem=\([0-9]*\)GB.*/\1/p' <<< "$prev")
  prev_wall=$(sed -n 's/.* walltime=\([0-9]*\):.*/\1/p' <<< "$prev")
  # Without an explicit override, never ask for less than last time.
  note=""
  if [[ -n "$MEM_OVERRIDE" ]]; then
    mem=$MEM_OVERRIDE
  else
    mem=$(sc_mem_gb "$dim")
    (( ${prev_mem:-0} > mem )) && mem=$prev_mem
    if [[ " $flags " == *" sigkill "* ]]; then mem=$(( mem * 3 / 2 )); note+=" (+50% mem after SIGKILL)"; fi
  fi
  queue=${QUEUE_OVERRIDE:-$(sc_queue_for_mem "$mem")} || die "$name needs ${mem}GB: more than one node"
  if [[ -n "$WALL_OVERRIDE" ]]; then
    wall=$WALL_OVERRIDE
  else
    wall=$(sc_walltime "$dim" "$nt" "$CBATCH")
    h=$((10#${wall%%:*})); ph=$((10#${prev_wall:-0})); (( ph > h )) && h=$ph
    if [[ " $flags " == *" walltime "* ]]; then h=$(( (h * 3 + 1) / 2 )); note+=" (+50% walltime after walltime kill)"; fi
    (( h > SC_WALLTIME_MAX_HOURS )) && h=$SC_WALLTIME_MAX_HOURS
    wall=$(printf '%02d:00:00' "$h")
  fi
  disk=$(sc_disk_gb "$dim"); disk_total=$((disk_total + disk))
  jobname="${VERSION//[^A-Za-z0-9]/}d${dim}t${nt}"   # e.g. v42d500t16 (short: old PBS limit 15 chars)
  (( CBATCH > 0 )) && jobname+="b${CBATCH}"

  cmd=(qsub -N "$jobname" -P "$SC_PROJECT" -q "$queue"
       -l "ncpus=$nt,mem=${mem}GB,walltime=$wall,storage=$SC_STORAGE,wd"
       -j oe -o "$cdir/pbs/$(date +%Y%m%dT%H%M%S).out"
       -v "SC_ROOT=$ROOT,SC_LABEL=$VERSION,SC_HII_DIM=$dim,SC_N_THREADS=$nt,SC_PHASES=$PHASES_PBS,SC_COEVAL_BATCH=$CBATCH,SC_EXTRA=$EXTRA_PBS,SC_RESULTS_ROOT=$RESULTS_ABS,SC_SIM_ROOT=$SIMS_ABS"
       "$HERE/job.pbs")
  if (( DRY )); then
    printf '%-23s %-9s %-8s %-9s %-10s %s\n' "$name" "$queue" "${mem}GB" "$wall" "${disk}GB" "dry-run$note"
    echo "    ${cmd[*]}"
  else
    mkdir -p "$cdir/pbs"
    jid=$("${cmd[@]}")
    echo "$(date -u +%FT%TZ) $jid queue=$queue ncpus=$nt mem=${mem}GB walltime=$wall phases=$PHASES extra=${EXTRA_PBS:-none}" >> "$cdir/pbs/jobids"
    printf '%-23s %-9s %-8s %-9s %-10s %s\n' "$name" "$queue" "${mem}GB" "$wall" "${disk}GB" "submitted $jid$note"
  fi
  n_sub=$((n_sub + 1))
done

echo
echo "$VERSION: $n_sub to run, $n_skip skipped. Peak disk if all run at once: ~${disk_total} GB under $SIMS_ABS (check with lquota)."
echo "Progress: python3 scaling/summarize.py --label $VERSION"
