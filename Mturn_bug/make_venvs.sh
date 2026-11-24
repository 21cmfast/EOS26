#!/bin/bash
# Build the two 21cmFAST 4.2 venvs used by Mturn_bug (on a Gadi login node, from the EOS26 root):
#
#   bash Mturn_bug/make_venvs.sh          # both
#   bash Mturn_bug/make_venvs.sh v4.2     # or one of them
#   bash Mturn_bug/make_venvs.sh v4.2fix
#
#   v4.2     21cmFAST 4.2 from PyPI, compiled from its source distribution
#   v4.2fix  git tag v4.2 with Mturn_bug/v4.2_mturn_fix.patch (the one-line fix)
#
# Both go through envs/create_venv_v4.3.sh, so they get the same compiler, modules
# and third-party packages (envs/constraints-gadi.txt, frozen from the former
# EOS26 v4.2 venv) as the EOS26 venvs. The v4.3 run uses the existing EOS26 venv
# (envs/use.sh v4.3), so nothing is built for it.
# Venvs: $MTURN_VENV_DIR/Mturn_bug-<label> (default /scratch/qp00/$USER/venvs).
# The patched build needs its own 21cmFAST clone ($MTURN_SRC, default
# /scratch/qp00/$USER/Mturn_bug_21cmFAST), which create_venv_v4.3.sh resets before patching.
# Add --force to rebuild a venv from scratch.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV_DIR="${MTURN_VENV_DIR:-/scratch/qp00/${USER}/venvs}"
SRC="${MTURN_SRC:-/scratch/qp00/${USER}/Mturn_bug_21cmFAST}"
WHICH="${1:-all}"
FORCE=(); [[ "${2:-}" == "--force" || "${1:-}" == "--force" ]] && FORCE=(--force)
[[ "$WHICH" == "--force" ]] && WHICH=all

if [[ "$WHICH" == all || "$WHICH" == v4.2 ]]; then
  echo "=== Mturn_bug v4.2: 21cmFAST 4.2 (PyPI)"
  V43_VERSION=4.2 V43_VENV="$VENV_DIR/Mturn_bug-v4.2" V43_USE_LABEL="(Mturn_bug) v4.2" \
    bash envs/create_venv_v4.3.sh gadi "${FORCE[@]}"
fi
if [[ "$WHICH" == all || "$WHICH" == v4.2fix ]]; then
  echo "=== Mturn_bug v4.2fix: git v4.2 + Mturn_bug/v4.2_mturn_fix.patch"
  [[ -d "$SRC/.git" ]] || git clone https://github.com/21cmfast/21cmFAST.git "$SRC"
  V43_GIT_REF=v4.2 V43_SRC="$SRC" V43_PATCH="$ROOT/Mturn_bug/v4.2_mturn_fix.patch" \
    V43_VENV="$VENV_DIR/Mturn_bug-v4.2fix" V43_USE_LABEL="(Mturn_bug) v4.2fix" \
    bash envs/create_venv_v4.3.sh gadi "${FORCE[@]}"
  # the patched line must be in the installed C source
  grep -q "M_turn_a = fmax(consts->mturn_a_nofb" "$SRC/src/py21cmfast/src/HaloBox.c" \
    || { echo "ERROR: patch not applied in $SRC" >&2; exit 1; }
fi
echo "Activate with: source Mturn_bug/env.sh v4.2|v4.2fix|v4.3"
