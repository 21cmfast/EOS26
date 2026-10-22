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
# Same rule as run_scripts/settings.py: $EOS26_DATA if set, /g/data/qp00/$USER
# on Gadi (scratch is too small; gdata I/O is as fast), else inside the repo.
if [[ -z "${SC_SIM_ROOT:-}" ]]; then
  if [[ -n "${EOS26_DATA:-}" ]]; then
    SC_SIM_ROOT="$EOS26_DATA/EOS26_scaling_sims"
  elif [[ "$(hostname)" == *gadi* || -d /g/data ]]; then
    SC_SIM_ROOT="/g/data/qp00/${USER:-$(id -un)}/EOS26_scaling_sims"
  else
    SC_SIM_ROOT="scaling/sims"
  fi
fi
SC_SEED=42

# --------------------------------------------------------- per 21cmFAST version
# Labels: v4.2, v4.3 (a 4.3.x release; 4.3.1 since 2026-10-21, while results/v4.3/
# was measured with 4.3.0), v4.3_patch (4.3.0 + the patch named in sc_patch
# below, built by envs/create_venv_v4.3_patch.sh; 4.3.1 contains the same fix) and
# v4.3_fftw (the v4.3 venv with USE_FFTW_WISDOM = true; FFTW wisdom files go to
# /g/data/qp00/$USER/fftw_wisdoms, see run_scripts/sim_steps.py). Results and simulation
# caches go to <root>/<label>/, so the labels never overwrite each other.
# Virtual environment holding each version (see envs/create_venv_v4.3.sh).
sc_venv() {
  if [[ -n "${SC_VENV_OVERRIDE:-}" ]]; then echo "$SC_VENV_OVERRIDE"; return; fi  # local testing only
  case "$1" in
    v4.2) echo "/scratch/qp00/${USER}/venvs/EOS26-intel" ;;       # production v4.2 venv
    v4.3) echo "/scratch/qp00/${USER}/venvs/EOS26-v4.3-intel" ;;
    v4.3_patch) echo "/scratch/qp00/${USER}/venvs/EOS26-v4.3_patch-intel" ;;
    v4.3_fftw) echo "/scratch/qp00/${USER}/venvs/EOS26-v4.3-intel" ;;   # same venv as v4.3
    *) return 1 ;;
  esac
}
# Parameter template for each version. 21cmFAST 4.3.x also reads EOS26.toml (same
# inputs, but a DeprecatedWarning for MIN_XE_FOR_FCOLL_IN_TAUX); the v4.3 copy uses
# the new name MIN_XE_FOR_NION_IN_TAUX.
sc_template() {
  case "$1" in
    v4.2) echo "EOS26.toml" ;;
    v4.3|v4.3_patch) echo "scaling/templates/EOS26_v4.3.toml" ;;
    v4.3_fftw) echo "scaling/templates/EOS26_v4.3_fftw.toml" ;;   # USE_FFTW_WISDOM = true
    *) return 1 ;;
  esac
}
# Regex the installed py21cmfast.__version__ must match (catches a wrong venv
# before any compute is spent). If your v4.2 venv was built from a git checkout
# (setuptools-scm version such as 4.2.1.dev84+g603e4efe), the v4.2 pattern still
# matches. v4.3 must be a 4.3.x release (PyPI, see envs/create_venv_v4.3.sh):
# pre-release builds of the release-v4.3 branch (4.3.devNNN) crash when a batched
# (resumed) coeval run continues (#791, #794) or differ from the release (FFTW
# threading #789, LW fix #799, FFTW clean-up, z > Z_HEAT_MAX changes).
sc_expect_version() {
  case "$1" in
    v4.2) echo '^4\.2' ;;
    v4.3|v4.3_fftw) echo '^4\.3\.[0-9]+$' ;;
    # A patched source build reports e.g. 4.3.1.dev0+gee535b94.d20261020 (dirty
    # tree); sc_patch is what actually identifies it.
    v4.3_patch) echo '^4\.3\.' ;;
    *) return 1 ;;
  esac
}
# Patch (relative to the repository root) that the label's py21cmfast must contain,
# or nothing. Checked by scaling/check_patch.py in launch.sh's preflight, in every
# job before measuring, and by envs/use.sh.
# v4.3.0_sfr_allzero.patch: the radiation-field check that read sfrd_acg of every
# past redshift back from disk at every step (bug_reports/5_v4.3_sfrd_history_reloaded.md).
sc_patch() {
  case "$1" in
    v4.3_patch) echo "envs/patches/v4.3.0_sfr_allzero.patch" ;;
    *) echo "" ;;
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
# launch.sh --follow: queue of the small follow-up job, and the longest chain.
SC_FOLLOW_QUEUE="normal"
SC_FOLLOW_MAX_ROUNDS=6
# Disk used by one configuration at its peak (IC + 92 PF + halos + 92 coevals),
# per HII cell: ~2.1 kB upstream + ~60 B per coeval (README storage table at
# HII_DIM=500: ICs 58 GB, PFs 92 x 2 GB, PHFs 25 GB, 7.5 GB per coeval; a v4.2
# HII_DIM=500 cache with 11 coevals measured ~330 GB) -> ~0.96 TB at 500.
# v4.3 writes the same boxes. Used for the launch.sh disk estimate only.
SC_DISK_BYTES_PER_CELL=7700
