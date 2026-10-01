#!/usr/bin/env python3
"""Status table and machine-readable summary of scaling measurements.

    python3 scaling/summarize.py                  # all labels
    python3 scaling/summarize.py --label v4.2     # one version

Prints one line per configuration (phase status, peak RSS per phase, where
the coeval peak happens) and writes, per label:

    scaling/results/<label>/summary_phases.csv   one row per (config, phase)
    scaling/results/<label>/summary_coeval_steps.csv
                                                 peak RSS of every coeval redshift

Only completed phases have numbers; nothing from an incomplete/partial
attempt is ever reported as a measurement. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import EOS26_ROOT, PHASES, fmt_bytes, fmt_seconds, parse_config_name, read_json  # noqa: E402

GIB = 1024**3
SYMBOL = {"complete": "ok", "running": "run", "failed": "FAIL", "interrupted": "int", "pending": "-"}

PHASE_FIELDS = (
    "label", "hii_dim", "n_threads", "coeval_batch", "phase", "status", "attempts", "peak_rss_bytes", "peak_rss_gib",
    "peak_rss_method", "baseline_rss_bytes", "wall_s", "cpu_s", "avg_cores", "n_steps", "peak_step_redshift",
    "product_bytes_total", "py21cmfast_version", "inputs_sha256", "host", "pbs_jobid", "finished_utc",
)
STEP_FIELDS = (
    "label", "hii_dim", "n_threads", "coeval_batch", "batch", "index", "redshift", "is_output", "peak_rss_bytes", "peak_rss_gib",
    "rss_after_bytes", "wall_s", "avg_cores", "halo_catalog_bytes", "includes_setup",
)


def summarize_label(label_dir: Path, quiet: bool) -> None:
    label = label_dir.name
    configs = sorted((d for d in label_dir.glob("HII_DIM_*_NT_*") if d.is_dir() and parse_config_name(d.name)),
                     key=lambda d: parse_config_name(d.name))
    if not configs:
        return
    phase_rows, step_rows = [], []
    if not quiet:
        print(f"\n== {label} ({len(configs)} configurations) ==")
        head = f"{'HII_DIM':>7} {'NT':>3} {'CB':>3}  " + " ".join(f"{p:>16}" for p in PHASES)
        print(head + f"  {'max peak':>10}  {'coeval peak z':>13}  notes")
    for cdir in configs:
        state = read_json(cdir / "state.json") or {}
        cfg = read_json(cdir / "config.json") or {}
        fp = cfg.get("fingerprint", {})
        dim, nt, cb = parse_config_name(cdir.name)
        cells, peaks, notes = [], {}, []
        for p in PHASES:
            st = (state.get("phases") or {}).get(p, {"status": "pending", "attempts": 0})
            res = read_json(cdir / "phases" / f"{p}.json") if st.get("status") == "complete" else None
            if res:
                peaks[p] = res["peak_rss_bytes"]
                cells.append(f"{res['peak_rss_bytes'] / GIB:8.2f}G {fmt_seconds(res['wall_s']):>6}")
                if res.get("peak_rss_method") != "vmhwm_reset":
                    notes.append(f"{p}:sampled")
            else:
                cells.append(f"{SYMBOL.get(st.get('status'), st.get('status')):>16}")
                if st.get("error"):
                    notes.append(f"{p}: {st['error']}")
            ps = (res or {}).get("peak_step") or {}
            phase_rows.append({
                "label": label, "hii_dim": dim, "n_threads": nt, "coeval_batch": cb, "phase": p,
                "status": st.get("status"),
                "attempts": st.get("attempts"),
                "peak_rss_bytes": (res or {}).get("peak_rss_bytes"),
                "peak_rss_gib": round(res["peak_rss_bytes"] / GIB, 4) if res else None,
                "peak_rss_method": (res or {}).get("peak_rss_method"),
                "baseline_rss_bytes": (res or {}).get("baseline_rss_bytes"),
                "wall_s": (res or {}).get("wall_s"), "cpu_s": (res or {}).get("cpu_s"),
                "avg_cores": (res or {}).get("avg_cores"), "n_steps": (res or {}).get("n_steps"),
                "peak_step_redshift": ps.get("redshift"),
                "product_bytes_total": (res or {}).get("product_bytes_total"),
                "py21cmfast_version": fp.get("py21cmfast_version"), "inputs_sha256": fp.get("inputs_sha256"),
                "host": ((res or {}).get("host") or {}).get("hostname"),
                "pbs_jobid": ((res or {}).get("host") or {}).get("pbs_jobid"),
                "finished_utc": (res or {}).get("finished_utc"),
            })
            if p == "coeval" and res:
                for s in res.get("steps", []):
                    if "redshift" not in s:
                        continue
                    step_rows.append({
                        "label": label, "hii_dim": dim, "n_threads": nt, "coeval_batch": cb,
                        "batch": s.get("batch"), "index": s["index"],
                        "redshift": s["redshift"], "is_output": s.get("is_output"),
                        "peak_rss_bytes": s["peak_rss_bytes"], "peak_rss_gib": round(s["peak_rss_bytes"] / GIB, 4),
                        "rss_after_bytes": s.get("rss_after_bytes"), "wall_s": s.get("wall_s"),
                        "avg_cores": s.get("avg_cores"), "halo_catalog_bytes": s.get("halo_catalog_bytes"),
                        "includes_setup": s.get("includes_setup", False),
                    })
        if not state:
            # measure.py never started for this configuration (it writes
            # state.json first thing): job still queued, or job.pbs failed early.
            jobids = cdir / "pbs" / "jobids"
            last = jobids.read_text().split("\n")[-2].split() if jobids.exists() and jobids.read_text().strip() else []
            jid = last[1] if len(last) > 1 else None
            logs = sorted((cdir / "pbs").glob("job_*.log")) + sorted((cdir / "pbs").glob("*.out"))
            notes.append(f"not started: job {jid} queued or failed early -> qstat -xf {jid}"
                         + (f"; see {logs[-1].relative_to(label_dir)}" if logs else "") if jid else "never submitted")
        if not quiet:
            top = max(peaks.values(), default=None)
            coeval = read_json(cdir / "phases" / "coeval.json") if "coeval" in peaks else None
            zpk = ((coeval or {}).get("peak_step") or {}).get("redshift")
            if state.get("complete") and not state.get("sim_deleted"):
                notes.append("sim kept")
            print(f"{dim:>7} {nt:>3} {cb if cb else '':>3}  " + " ".join(cells) + f"  {fmt_bytes(top) if top else '':>10}  "
                  f"{(f'{zpk:.2f}' if zpk is not None else ''):>13}  {'; '.join(notes)}")
    for name, fields, rows in (("summary_phases.csv", PHASE_FIELDS, phase_rows),
                               ("summary_coeval_steps.csv", STEP_FIELDS, step_rows)):
        with (label_dir / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    if not quiet:
        print(f"(peak RSS [GiB] and wall time per completed phase; wrote {label_dir}/summary_*.csv)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-root", type=Path, default=Path("scaling/results"))
    ap.add_argument("--label", default=None, help="only this version label (default: all)")
    ap.add_argument("--quiet", action="store_true", help="only write the CSV files")
    args = ap.parse_args()
    root = args.results_root if args.results_root.is_absolute() else EOS26_ROOT / args.results_root
    if not root.is_dir():
        print(f"no results yet under {root}")
        return 0
    labels = [root / args.label] if args.label else sorted(d for d in root.iterdir() if d.is_dir())
    for label_dir in labels:
        if label_dir.is_dir():
            summarize_label(label_dir, args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
