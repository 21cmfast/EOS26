#!/bin/bash
# 21cmFAST 4.3.0 + envs/patches/v4.3.0_sfr_allzero.patch in its own venv: the
# scaling label v4.3_patch, and production with EOS26_VERSION=v4.3_patch.
#
#   bash envs/create_venv_v4.3_patch.sh gadi [--force]
#   bash envs/create_venv_v4.3_patch.sh mac  [--force]
#
# A source build of the v4.3.0 tag (envs/create_venv_v4.3.sh with V43_GIT_REF and
# V43_PATCH) in a dedicated clone, 21cmFASTv4.3-patch/, which is reset before
# patching. The released v4.3 venv and its clone are not touched.
# The patch: bug_reports/5_v4.3_sfrd_history_reloaded.md.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET=${1:-}
PATCH="${V43_PATCH:-$ROOT/envs/patches/v4.3.0_sfr_allzero.patch}"
case "$TARGET" in
  gadi)
    # shellcheck source=../scaling/config.sh
    source "$ROOT/scaling/config.sh"
    VENV=$(sc_venv v4.3_patch) ;;
  mac) VENV="$ROOT/.venv-v4.3_patch" ;;
  *) echo "usage: bash envs/create_venv_v4.3_patch.sh gadi|mac [--force]" >&2; exit 1 ;;
esac

V43_GIT_REF="${V43_GIT_REF:-v4.3.0}" V43_PATCH="$PATCH" \
V43_SRC="${V43_SRC:-$ROOT/21cmFASTv4.3-patch}" V43_VENV="$VENV" V43_USE_LABEL=v4.3_patch \
  bash "$ROOT/envs/create_venv_v4.3.sh" "$@"

"$VENV/bin/python" "$ROOT/scaling/check_patch.py" "$PATCH"
echo "Scaling with this build:  bash scaling/campaign_v4.3_patch.sh  (or launch.sh --version v4.3_patch)"
