"""Check that the py21cmfast this python imports contains a patch (its added lines).

    python scaling/check_patch.py envs/patches/v4.3.0_sfr_allzero.patch

Used for patched-build labels (sc_patch in scaling/config.sh): launch.sh runs it in
its preflight, job.pbs before measuring, envs/use.sh after activating. Exit status 1
if any added line is missing. Doesn't import py21cmfast, so it takes no time.
"""
import importlib.util
import sys
from pathlib import Path


def added_lines(patch: Path) -> dict[str, list[str]]:
    """Map 'drivers/single_field.py' -> stripped non-empty lines the patch adds."""
    files: dict[str, list[str]] = {}
    cur = None
    for line in patch.read_text().splitlines():
        if line.startswith("+++ "):
            path = line[4:].split("\t")[0]
            cur = files.setdefault(path.split("py21cmfast/", 1)[1], []) if "py21cmfast/" in path else None
        elif cur is not None and line.startswith("+") and line[1:].strip():
            cur.append(line[1:].strip())
    return files


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    patch = Path(sys.argv[1])
    spec = importlib.util.find_spec("py21cmfast")
    if spec is None or spec.origin is None:
        print("check_patch: py21cmfast is not installed in this python", file=sys.stderr)
        return 1
    pkg = Path(spec.origin).parent
    files = added_lines(patch)
    if not files:
        print(f"check_patch: {patch} changes no py21cmfast file", file=sys.stderr)
        return 1
    missing = []
    for rel, lines in files.items():
        target = pkg / rel
        have = {x.strip() for x in target.read_text().splitlines()} if target.exists() else set()
        missing += [f"  {rel}: {x}" for x in lines if x not in have]
    if missing:
        print(f"check_patch: {pkg} does not contain {patch.name}; missing lines:", *missing[:5], sep="\n",
              file=sys.stderr)
        return 1
    print(f"check_patch: {patch.name} is applied in {pkg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
