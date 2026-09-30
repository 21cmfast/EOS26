# shellcheck shell=bash
# Switch between the 21cmFAST v4.2 and v4.3 virtual environments.
#
#   source envs/use.sh v4.2
#   source envs/use.sh v4.3
#
# Mac: .venv (v4.2, the uv project env) and .venv-v4.3.
# Gadi: the venvs named in scaling/config.sh (sc_venv), plus the modules they need.
#
# With a venv activated, run scripts with `python ...` or
# `uv run --no-sync --active ...`. Never run a plain `uv sync` / `uv run` (without
# --no-sync) against the v4.3 venv: uv would re-install 21cmfast==4.2 from uv.lock.

_eos26_use() {
  local ver=$1 root venv
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  case "$ver" in v4.2|v4.3) ;; *) echo "usage: source envs/use.sh v4.2|v4.3" >&2; return 1 ;; esac
  if [[ -d /scratch/qp00 ]]; then          # Gadi
    # shellcheck source=../scaling/config.sh
    source "$root/scaling/config.sh"
    venv=$(sc_venv "$ver")
    if command -v module >/dev/null 2>&1; then
      module purge
      local m; for m in $SC_MODULES; do module load "$m"; done
    fi
  else                                     # laptop
    if [[ "$ver" == v4.2 ]]; then venv="$root/.venv"; else venv="$root/.venv-v4.3"; fi
  fi
  [[ -f "$venv/bin/activate" ]] || { echo "no venv at $venv (see envs/create_venv_v4.3.sh)" >&2; return 1; }
  command -v deactivate >/dev/null 2>&1 && deactivate
  # shellcheck disable=SC1091
  source "$venv/bin/activate"
  python -W ignore -c "import py21cmfast as p; print('21cmFAST', p.__version__, '->', p.__file__)"
}
_eos26_use "${1:-}"
