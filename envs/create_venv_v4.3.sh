#!/bin/bash
# Create a second uv virtual environment with 21cmFAST v4.3, next to the
# existing v4.2 one, so the two versions can be switched between.
#
#   bash envs/create_venv_v4.3.sh mac     # on your Mac, from the EOS26 folder
#   bash envs/create_venv_v4.3.sh gadi    # on a Gadi login node, from /scratch/qp00/$USER/EOS26
#
# What it does (each step is echoed):
#   1. check out 21cmFAST's release-v4.3 branch at a PINNED commit
#      (v4.3 is not on PyPI; setuptools-scm reports it as 4.3.dev287+g3f0289071),
#   2. freeze the existing v4.2 venv's third-party packages into a constraints
#      file, so v4.3 gets *identical* numpy/scipy/h5py/classy/hmf/... and the
#      21cmFAST version is the only difference between the two environments,
#   3. create the new venv with uv and build 21cmFAST v4.3 into it (non-editable,
#      so later edits of the source tree cannot change the installed code),
#   4. print the installed version and write a full freeze for provenance.
#
# Switching between versions afterwards: see envs/use.sh
#   source envs/use.sh v4.2   |   source envs/use.sh v4.3
#
# Re-running is safe: an existing venv is upgraded in place to the pinned commit
# (21cmFAST is rebuilt, the other packages stay as they are); add --force to
# delete and rebuild it from scratch.
#
# Optional overrides (environment variables), e.g. for a patched test build:
#   V43_COMMIT commit to build (default: the pin below; "latest" = the current
#              head of release-v4.3, recorded in the freeze file)
#   V43_SRC    source checkout to build from        (default: 21cmFASTv4.3/)
#   V43_REPO   where to clone it from if missing   (default: GitHub)
#   V43_VENV   venv to create                       (default: .venv-v4.3 / EOS26-v4.3-intel)
#   V43_PATCH  patch applied on top of the pinned commit (V43_SRC must then be a
#              dedicated clone: it is reset to the commit before patching)

set -euo pipefail

TARGET=${1:-}
FORCE=0; [[ "${2:-}" == "--force" ]] && FORCE=1

# ---- pinned 21cmFAST v4.3 source -------------------------------------------------
V43_REPO="${V43_REPO:-https://github.com/21cmfast/21cmFAST.git}"
V43_BRANCH="release-v4.3"
# release-v4.3 head on 2026-10-01 (merge of #792, which fixes the resume TypeError #791).
# Previous pin: d45dc4020fa88795b068b584fe927b3d240f371d (2026-09-30).
V43_COMMIT="${V43_COMMIT:-3f0289071a5e830260248e05e60e3353ad80c84d}"

EOS26_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
V43_SRC="${V43_SRC:-$EOS26_ROOT/21cmFASTv4.3}"
V43_PATCH="${V43_PATCH:-}"
[[ -z "$V43_PATCH" || -f "$V43_PATCH" ]] || { echo "patch not found: $V43_PATCH" >&2; exit 1; }
[[ -z "$V43_PATCH" ]] || V43_PATCH="$(cd "$(dirname "$V43_PATCH")" && pwd)/$(basename "$V43_PATCH")"

case "$TARGET" in
  mac)
    V42_VENV="${V42_VENV:-$EOS26_ROOT/.venv}"            # uv project venv (21cmfast==4.2 from uv.lock)
    V43_VENV="${V43_VENV:-$EOS26_ROOT/.venv-v4.3}"
    EXTRA_PKGS="psutil matplotlib ipykernel"
    # Same toolchain as for the v4.2 build. build_cffi.py adds every environment
    # variable whose NAME contains "inc"/"lib" as an include/library directory.
    if command -v brew >/dev/null 2>&1; then
      BREW=$(brew --prefix)
      export CC="${CC:-clang}"
      export BREW_INC="${BREW_INC:-$BREW/include}" BREW_LIB="${BREW_LIB:-$BREW/lib}"
      if [[ -d "$BREW/opt/libomp" ]]; then
        export LIBOMP_INC="${LIBOMP_INC:-$BREW/opt/libomp/include}" LIBOMP_LIB="${LIBOMP_LIB:-$BREW/opt/libomp/lib}"
      fi
    fi
    ;;
  gadi)
    V42_VENV="${V42_VENV:-/scratch/qp00/${USER}/venvs/EOS26-intel}"     # production v4.2 venv
    V43_VENV="${V43_VENV:-/scratch/qp00/${USER}/venvs/EOS26-v4.3-intel}"   # = sc_venv v4.3 in scaling/config.sh
    EXTRA_PKGS="psutil matplotlib"
    export PATH="$HOME/.local/bin:$PATH"                    # uv
    if command -v module >/dev/null 2>&1; then
      module purge
      module load intel-compiler/2021.8.0 gsl/2.7.1 fftw3/3.3.10
    fi
    # Use the SAME C compiler that built the v4.2 venv, so v4.2 vs v4.3 compares
    # 21cmFAST versions and not compilers. Step 0 below prints what built v4.2;
    # set CC accordingly before running this script if the default is wrong,
    # e.g.   CC=icx bash envs/create_venv_v4.3.sh gadi
    export CC="${CC:-icx}"
    ;;
  *)
    sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac

run() { echo "+ $*"; "$@"; }

command -v uv >/dev/null || { echo "uv not found (https://docs.astral.sh/uv/)" >&2; exit 1; }
[[ -x "$V42_VENV/bin/python" ]] || { echo "v4.2 venv not found: $V42_VENV" >&2; exit 1; }
mkdir -p "$EOS26_ROOT/envs"
HOST_TAG=$(hostname -s 2>/dev/null || hostname)

echo "== 0. what built the v4.2 venv (compiler of its C extension)"
"$V42_VENV/bin/python" - <<'PY' || true
import pathlib, subprocess, py21cmfast as p
so = next(pathlib.Path(p.__file__).parent.glob("c_21cmfast*"), None)
print("v4.2 py21cmfast", p.__version__, "|", so)
if so:
    for tool in (["readelf", "-p", ".comment", str(so)], ["strings", str(so)]):
        try:
            out = subprocess.run(tool, capture_output=True, text=True, check=False).stdout
        except FileNotFoundError:
            continue
        hits = sorted({l.strip() for l in out.splitlines() if any(k in l for k in ("GCC:", "Intel(R)", "clang version"))})
        if hits:
            print("  built with:", *hits[:3], sep="\n    ")
            break
PY
echo "   building v4.3 with CC=${CC:-<default>}"

echo "== 1. 21cmFAST source at $V43_COMMIT"
if [[ ! -d "$V43_SRC/.git" ]]; then
  run git clone --branch "$V43_BRANCH" "$V43_REPO" "$V43_SRC"
fi
if [[ -n "$V43_PATCH" ]]; then
  # Dedicated clone for a patched build: always start from the pinned commit.
  run git -C "$V43_SRC" reset --quiet --hard
elif [[ -n "$(git -C "$V43_SRC" status --porcelain --untracked-files=no)" ]]; then
  echo "ERROR: $V43_SRC has local modifications; commit/stash them first" >&2; exit 1
fi
run git -C "$V43_SRC" fetch --quiet origin "$V43_BRANCH" || echo "   (fetch failed; using local clone)"
if [[ "$V43_COMMIT" == latest ]]; then
  V43_COMMIT=$(git -C "$V43_SRC" rev-parse "origin/$V43_BRANCH")
  echo "   latest $V43_BRANCH = $V43_COMMIT"
fi
has_commit() { git -C "$V43_SRC" cat-file -e "${V43_COMMIT}^{commit}" 2>/dev/null; }
if ! has_commit; then
  # A clone of a local clone (V43_REPO=<path>) only sees that clone's own
  # branches: also try its remote-tracking branch, then GitHub itself.
  git -C "$V43_SRC" fetch --quiet origin "refs/remotes/origin/$V43_BRANCH" 2>/dev/null || true
  has_commit || run git -C "$V43_SRC" fetch --quiet https://github.com/21cmfast/21cmFAST.git "$V43_BRANCH" || true
fi
run git -C "$V43_SRC" checkout --quiet --detach "$V43_COMMIT"
git -C "$V43_SRC" log -1 --format='   %H %cd %s' --date=short
if [[ -n "$V43_PATCH" ]]; then
  run git -C "$V43_SRC" apply "$V43_PATCH"
  echo "   patched with $(basename "$V43_PATCH") (reported version gets a .dYYYYMMDD 'dirty' suffix)"
fi

echo "== 2. constraints = third-party packages of the v4.2 venv"
CONSTRAINTS="$EOS26_ROOT/envs/constraints-from-v4.2-${TARGET}.txt"
uv pip freeze --python "$V42_VENV/bin/python" \
  | grep -v -i -E '^(21cmfast|eos26)([ =@]|$)|^-e ' > "$CONSTRAINTS"
echo "   $(wc -l < "$CONSTRAINTS") pins -> $CONSTRAINTS"

echo "== 3. venv $V43_VENV"
if [[ -d "$V43_VENV" ]]; then
  if (( FORCE )); then run rm -rf "$V43_VENV"; else echo "   exists (use --force to rebuild); installing into it"; fi
fi
# Same base interpreter (exact Python version) as the v4.2 venv.
BASE_PY=$("$V42_VENV/bin/python" -c 'import sys; print(sys._base_executable)')
echo "   base interpreter: $BASE_PY ($("$BASE_PY" -V 2>&1))"
[[ -d "$V43_VENV" ]] || run uv venv "$V43_VENV" --python "$BASE_PY" --prompt "EOS26-v4.3"
# --refresh/--reinstall: never reuse a wheel uv cached from another checkout.
# shellcheck disable=SC2086  # EXTRA_PKGS is a word list
run uv pip install --python "$V43_VENV/bin/python" \
  --refresh-package 21cmfast --reinstall-package 21cmfast \
  -c "$CONSTRAINTS" "$V43_SRC" $EXTRA_PKGS

echo "== 4. check"
"$V43_VENV/bin/python" -W ignore -c "import py21cmfast as p; print('   py21cmfast', p.__version__, p.__file__)"
FREEZE="$EOS26_ROOT/envs/freeze-$(basename "$V43_VENV" | sed 's/^\.//')-${TARGET}-${HOST_TAG}.txt"
uv pip freeze --python "$V43_VENV/bin/python" > "$FREEZE"
echo "   full freeze -> $FREEZE"
echo
echo "Done. Activate with:  source envs/use.sh v4.3"
