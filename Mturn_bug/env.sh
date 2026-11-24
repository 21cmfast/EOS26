# shellcheck shell=bash
# Activate the 21cmFAST environment of one Mturn_bug run (from the EOS26 root):
#
#   source Mturn_bug/env.sh v4.2      # 21cmFAST 4.2 (PyPI release)
#   source Mturn_bug/env.sh v4.2fix   # 21cmFAST 4.2 + Mturn_bug/v4.2_mturn_fix.patch
#   source Mturn_bug/env.sh v4.3      # the EOS26 production venv (21cmFAST 4.3.1, envs/use.sh)
#
# The v4.2 and v4.2fix venvs are built once on Gadi with Mturn_bug/make_venvs.sh, in
# $MTURN_VENV_DIR (default /scratch/qp00/$USER/venvs). Elsewhere the default is ~/venvs.

_mturn_env() {
  local ver=$1 root venv
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  case "$ver" in
    v4.3)
      # shellcheck source=../envs/use.sh
      source "$root/envs/use.sh" v4.3
      return
      ;;
    v4.2|v4.2fix) ;;
    *) echo "usage: source Mturn_bug/env.sh v4.2|v4.2fix|v4.3" >&2; return 1 ;;
  esac
  if [[ -d /scratch/qp00 ]]; then          # Gadi
    venv="${MTURN_VENV_DIR:-/scratch/qp00/${USER}/venvs}/Mturn_bug-$ver"
    # shellcheck source=../scaling/config.sh
    source "$root/scaling/config.sh"
    if command -v module >/dev/null 2>&1; then
      module purge
      local m; for m in $SC_MODULES; do module load "$m"; done
    fi
  else
    venv="${MTURN_VENV_DIR:-$HOME/venvs}/Mturn_bug-$ver"
  fi
  [[ -f "$venv/bin/activate" ]] || { echo "no venv at $venv (see Mturn_bug/make_venvs.sh)" >&2; return 1; }
  command -v deactivate >/dev/null 2>&1 && deactivate
  # shellcheck disable=SC1091
  source "$venv/bin/activate"
  python -W ignore -c "import py21cmfast as p; print('21cmFAST', p.__version__, '->', p.__file__)"
}
_mturn_env "${1:-}"
