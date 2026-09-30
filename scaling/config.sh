# shellcheck shell=bash
# shellcheck disable=SC2034  # variables are used by the scripts that source this file
# Site / campaign settings for the EOS26 scaling measurements (sourced by
# launch.sh and job.pbs). Edit here, not in the scripts.
#
# Plain functions instead of associative arrays so this also sources under
# macOS's bash 3.2.

# ---------------------------------------------------------------- PBS / Gadi
SC_PROJECT="qp00"
SC_STORAGE="scratch/qp00+gdata/qp00"
SC_MODULES="intel-compiler/2021.8.0 gsl/2.7.1 fftw3/3.3.10"

# ------------------------------------------------------------------- paths
# Relative paths are relative to the EOS26 repository root.
SC_RESULTS_ROOT="${SC_RESULTS_ROOT:-scaling/results}"
# Simulation caches. MUST be persistent storage (not $PBS_JOBFS): resuming an
# interrupted configuration re-uses the products of its completed phases.
SC_SIM_ROOT="${SC_SIM_ROOT:-scaling/sims}"
SC_SEED=42

# --------------------------------------------------------- per 21cmFAST version
# Virtual environment holding each version (see envs/create_venv_v4.3.sh).
sc_venv() {
  if [[ -n "${SC_VENV_OVERRIDE:-}" ]]; then echo "$SC_VENV_OVERRIDE"; return; fi  # local testing only
  case "$1" in
    v4.2) echo "/scratch/qp00/${USER}/venvs/EOS26-intel" ;;       # production v4.2 venv
    v4.3) echo "/scratch/qp00/${USER}/venvs/EOS26-v4.3-intel" ;;
    *) return 1 ;;
  esac
}
# Parameter template for each version (v4.3 needs one renamed parameter).
sc_template() {
  case "$1" in
    v4.2) echo "EOS26.toml" ;;
    v4.3) echo "scaling/templates/EOS26_v4.3.toml" ;;
    *) return 1 ;;
  esac
}
# Regex the installed py21cmfast.__version__ must match (catches a wrong venv
# before any compute is spent). A source build of 21cmFAST reports a
# setuptools-scm version such as 4.3.dev279+gd45dc4020; if your v4.2 venv was
# built from a git checkout, adjust the v4.2 pattern accordingly.
sc_expect_version() {
  case "$1" in
    v4.2) echo '^4\.2' ;;
    v4.3) echo '^4\.3' ;;
    *) return 1 ;;
  esac
}

# ------------------------------------------------ PBS resource request model
# Only used to SIZE the PBS request -- never as a measurement.
# Memory: coeval peak RSS ~ 950 B per HII cell for EOS26 in v4.2 (full-evolution
# runs at HII_DIM 200-500: 920-970 B/cell), times a safety factor.
SC_MEM_BYTES_PER_CELL=950
SC_MEM_SAFETY=1.4
SC_MEM_OVERHEAD_GB=4
SC_MEM_MIN_GB=8
# Queue by requested memory (Gadi Cascade Lake: 48 cores/node for all three).
SC_QUEUE_NORMAL_MAX_GB=190
SC_QUEUE_HUGEMEM_MAX_GB=1470
SC_QUEUE_MEGAMEM_MAX_GB=2990
# Walltime [h] at N_THREADS >= 16, by HII_DIM (upper bounds, generous).
# Fewer threads scale it by (16/N_THREADS)^0.7. Capped at 48 h (Gadi limit).
sc_walltime_base_hours() {
  local d=$1
  if   (( d <= 100 )); then echo 2
  elif (( d <= 200 )); then echo 5
  elif (( d <= 300 )); then echo 10
  elif (( d <= 400 )); then echo 20
  elif (( d <= 500 )); then echo 36
  else echo 48
  fi
}
SC_WALLTIME_MAX_HOURS=48
SC_WALLTIME_BATCH_FACTOR=3   # for --coeval-batch configurations
# Automatic retries by launch.sh: after a SIGKILL (memory) the next submission
# asks for 50% more memory, after a walltime kill for 50% more walltime. A
# configuration whose unfinished phase has been attempted SC_MAX_ATTEMPTS times
# is not resubmitted until you look at it (then use launch.sh --retry).
SC_MAX_ATTEMPTS=3
# Disk used by one configuration at its peak (IC + 92 PF + halos + 92 coevals),
# ~7.2 kB per HII cell in v4.2 (HII_DIM=300: ~190 GiB). Only for a warning.
SC_DISK_BYTES_PER_CELL=7200
