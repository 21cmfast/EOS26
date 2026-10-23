#!/usr/bin/env python3
"""Fold PBS job output files (<jobname>.o<jobid>, .e<jobid>) into the job's log, then delete them.

    python pbs_scripts/fold_pbs_output.py --dry-run   # show what would happen
    python pbs_scripts/fold_pbs_output.py

PBS writes each job's stdout and stderr to <jobname>.o<jobid> / .e<jobid> in the
directory it was submitted from (git ignores them). Most of that repeats the job's log,
but some of it is only there: the PBS resource summary at the end of .o (exit status,
memory used, walltime), the compare_* check results (printed, not logged) and tracebacks
in .e. For every such file in the repository root, logs/ and scaling/logs/, this appends
to the log with the same job id
  * the stdout lines that are not already in the log (progress bars dropped),
  * stderr, apart from the "Currently Loaded Modulefiles" list,
  * the PBS resource summary,
and deletes the .o/.e files. A job with several logs (full_test: ICs, PFs, PHFs, coevals,
lightcone) gets it in the one of its last step. A job without a log gets
logs/<jobname>_<jobid>.log (logs/HII_DIM200_reference/ for the HII_DIM=200 test jobs,
scaling/logs/ for the FFT benchmark). Run it on Gadi before committing logs.
Standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIRS = [ROOT / "logs", ROOT / "scaling" / "logs"]
PBS_FILE = re.compile(r"^(?P<name>.+)\.(?P<kind>[oe])(?P<jid>\d+)$")
STEP_ORDER = ("lightcone", "coevals", "compare", "PHFs", "PFs", "ICs")  # last step first
TEST_JOBS = ("full_test", "rt_test")


def dest_for_new_log(name: str, jid: str) -> Path:
    if "fft_bench" in name:
        d = ROOT / "scaling" / "logs"
    elif any(t in name for t in TEST_JOBS):
        d = ROOT / "logs" / "HII_DIM200_reference"
    else:
        d = ROOT / "logs"
    return d / f"{name.replace('.', '_')}_{jid}.log"


def find_log(jid: str) -> Path | None:
    pat = re.compile(rf"(^|_){jid}(_|\.log$)")
    logs = [p for d in LOG_DIRS if d.exists() for p in d.rglob("*.log") if pat.search(p.name)]
    if not logs:
        return None

    def rank(p: Path) -> int:
        return next((i for i, s in enumerate(STEP_ORDER) if f"_{s}" in p.stem), len(STEP_ORDER))

    return min(logs, key=lambda p: (rank(p), p.name))


def split_summary(text: str) -> tuple[list[str], list[str]]:
    """stdout lines before the PBS resource summary, and the summary itself."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "Resource Usage on" in line:
            start = i - 1 if i > 0 and set(lines[i - 1].strip()) == {"="} else i
            return lines[:start], lines[start:]
    return lines, []


def fold(name: str, jid: str, files: dict[str, Path], dry_run: bool) -> str:
    log = find_log(jid)
    new = log is None
    if new:
        log = dest_for_new_log(name, jid)
    known = set()
    if not new:
        with open(log, errors="replace") as f:
            known = {line.strip() for line in f}
    out, summary = split_summary(files["o"].read_text(errors="replace")) if "o" in files else ([], [])
    out = [l.rstrip() for l in out if l.strip() and l.strip() not in known and "━" not in l]
    err = []
    if "e" in files:
        err = [l.rstrip() for l in files["e"].read_text(errors="replace").splitlines()
               if l.strip() and "Currently Loaded Modulefiles" not in l
               and not re.match(r"^\s*\d+\)\s+\S+/\S+", l)]
    parts = [f"\n==== PBS output of job {jid} ({', '.join(p.name for p in files.values())}), "
             "folded in by pbs_scripts/fold_pbs_output.py ===="]
    if out:
        parts += ["---- stdout not already in this log ----", *out]
    if err:
        parts += ["---- stderr ----", *err]
    if summary:
        parts += ["---- PBS resource summary ----", *summary]
    what = f"{len(out)} stdout, {len(err)} stderr, {'summary' if summary else 'no summary'}"
    if not dry_run:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a") as f:
            f.write("\n".join(parts) + "\n")
        for p in files.values():
            p.unlink()
    return f"{' + '.join(p.relative_to(ROOT).as_posix() for p in files.values())} -> " \
           f"{log.relative_to(ROOT).as_posix()}{' (new)' if new else ''}: {what}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    jobs: dict[tuple[str, str], dict[str, Path]] = defaultdict(dict)
    for d in [ROOT, *LOG_DIRS]:
        if not d.exists():
            continue
        for p in (d.glob("*") if d == ROOT else d.rglob("*")):
            m = PBS_FILE.match(p.name)
            if p.is_file() and m:
                jobs[(m["name"], m["jid"])][m["kind"]] = p
    if not jobs:
        print("no PBS output files")
        return
    for (name, jid), files in sorted(jobs.items(), key=lambda kv: kv[0][1]):
        files = {k: files[k] for k in ("o", "e") if k in files}
        print(("would fold " if args.dry_run else "folded ") + fold(name, jid, files, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
