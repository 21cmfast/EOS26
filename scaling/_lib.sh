# shellcheck shell=bash
# Helpers shared by launch.sh and job.pbs. Requires config.sh to be sourced first.

# Absolute path: relative paths are taken relative to the EOS26 root ($1).
sc_abs() {
  local root=$1 p=$2
  if [[ "$p" = /* ]]; then echo "$p"; else echo "$root/$p"; fi
}

# sc_config_name HII_DIM N_THREADS [COEVAL_BATCH]   (must match _common.config_name)
sc_config_name() {
  printf 'HII_DIM_%04d_NT_%02d' "$1" "$2"
  if (( ${3:-0} > 0 )); then printf '_CB%02d' "$3"; fi
  echo
}

# sc_config_dir ROOT LABEL HII_DIM N_THREADS [COEVAL_BATCH]
sc_config_dir() {
  echo "$(sc_abs "$1" "$SC_RESULTS_ROOT")/$2/$(sc_config_name "$3" "$4" "${5:-0}")"
}

# Estimated memory request [GB] for HII_DIM ($1).
sc_mem_gb() {
  awk -v d="$1" -v b="$SC_MEM_BYTES_PER_CELL" -v s="$SC_MEM_SAFETY" \
      -v o="$SC_MEM_OVERHEAD_GB" -v m="$SC_MEM_MIN_GB" \
      'BEGIN { g = s * b * d^3 / 1e9 + o; g = (g < m) ? m : g; printf "%d\n", (g == int(g)) ? g : int(g) + 1 }'
}

# Queue able to hold MEM_GB ($1); fails if nothing can.
sc_queue_for_mem() {
  local g=$1
  if   (( g <= SC_QUEUE_NORMAL_MAX_GB ));  then echo normal
  elif (( g <= SC_QUEUE_HUGEMEM_MAX_GB )); then echo hugemem
  elif (( g <= SC_QUEUE_MEGAMEM_MAX_GB )); then echo megamem
  else return 1
  fi
}

# Walltime (HH:MM:SS) for HII_DIM ($1), N_THREADS ($2) [, COEVAL_BATCH ($3)].
# Batched coevals re-establish the history from the cache in every batch (in
# v4.2 that includes recomputing the uncached X-ray boxes): x SC_WALLTIME_BATCH_FACTOR.
sc_walltime() {
  local base
  base=$(sc_walltime_base_hours "$1")
  (( ${3:-0} > 0 )) && base=$(( base * SC_WALLTIME_BATCH_FACTOR ))
  awk -v b="$base" -v n="$2" -v cap="$SC_WALLTIME_MAX_HOURS" \
      'BEGIN { f = (n < 16) ? (16 / n)^0.7 : 1; h = b * f; h = (h > cap) ? cap : h;
               h = (h == int(h)) ? h : int(h) + 1; printf "%02d:00:00\n", h }'
}

# Disk estimate [GB] for HII_DIM ($1).
sc_disk_gb() {
  awk -v d="$1" -v b="$SC_DISK_BYTES_PER_CELL" 'BEGIN { printf "%d\n", b * d^3 / 1e9 + 1 }'
}

# True if PBS job $1 is still queued/running/held/exiting.
sc_job_active() {
  local jid=$1 st
  [[ -n "$jid" ]] || return 1
  command -v qstat >/dev/null 2>&1 || return 1
  st=$(qstat -f "$jid" 2>/dev/null | awk -F' = ' '/^[[:space:]]*job_state/ {print $2; exit}')
  [[ -n "$st" && "$st" != F && "$st" != X && "$st" != M ]]
}

sc_load_modules() {
  if command -v module >/dev/null 2>&1; then
    module purge
    local m
    for m in $SC_MODULES; do module load "$m"; done
  fi
}

# Flags describing a configuration, from its state.json and newest PBS output:
#   complete   all phases measured
#   sigkill    last attempt was SIGKILLed: a worker killed by signal 9, or the
#              PBS epilogue says "Exit Status: 137" (Gadi: memory limit)
#   walltime   the newest PBS job hit its walltime (Gadi: "Exit Status: -29")
#   retries    some unfinished phase has already been attempted >= SC_MAX_ATTEMPTS times
sc_state_flags() {
  local cdir=$1 f out=""
  for f in "$cdir"/pbs/*.out; do [[ -f "$f" ]] && out=$f; done   # names are timestamps: last = newest
  python3 - "$cdir/state.json" "${out:-}" "${SC_MAX_ATTEMPTS:-3}" <<'PY'
import json, re, sys
state_path, out_path, max_attempts = sys.argv[1], sys.argv[2], int(sys.argv[3])
try:
    s = json.load(open(state_path))
except Exception:
    s = {}
phases = s.get("phases", {}).values()
flags = []
if s.get("complete"):
    flags.append("complete")
pbs = ""
if out_path:
    try:
        pbs = open(out_path, errors="replace").read()[-20000:]
    except OSError:
        pass
if any(p.get("status") == "failed" and "signal 9" in (p.get("error") or "") for p in phases) \
        or re.search(r"Exit Status:\s+137\b", pbs):
    flags.append("sigkill")
if re.search(r"Exit Status:\s+-29\b|exceed\w* walltime", pbs, re.I):
    flags.append("walltime")
if not s.get("complete") and any(p.get("status") != "complete" and p.get("attempts", 0) >= max_attempts
                                 for p in phases):
    flags.append("retries")
print(" ".join(flags))
PY
}
