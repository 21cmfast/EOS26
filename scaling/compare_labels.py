#!/usr/bin/env python3
"""Compare two scaling labels config by config: wall time and peak memory per phase.

    python3 scaling/summarize.py --label v4.3_patch --quiet   # refresh the CSVs
    python3 scaling/summarize.py --label v4.3_fftw --quiet
    python3 scaling/compare_labels.py v4.3_patch v4.3_fftw

Made for the FFTW wisdom decision (v4.3_fftw = v4.3.1 with USE_FFTW_WISDOM = true,
v4.3_patch = the same code without it), but works for any two labels. For every
configuration (HII_DIM, threads, batch) that both labels completed, it prints

  * per phase: wall time of A and B, B/A, and peak RSS of A and B;
  * coeval steps: median B/A of the per-redshift wall time (steady-state steps only,
    the first step of each process includes the setup) and B - A of the first step.

With wisdom on, the FFTW_PATIENT planning runs in the first process that broadcasts
a given FFT size and thread count (normally the ICs phase), for the hires box
(DIM = 3 HII_DIM) and the lowres box; later processes load the saved plans. So
"ICs B - A" is mostly the planning time of the hires DIM^3 r2c + c2r plans, minus
any speed-up of the ICs FFTs. The last block fits that difference as a power law of
DIM and extrapolates it to DIM = 4500 (the HII_DIM = 1500 hires box); the coeval phase
does not make those plans (sim_steps._create_coeval_wisdoms). Wall times come from
different nodes and days, so differences of a few percent are noise.
Standard library only.
"""

from __future__ import annotations

import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"
PHASES = ("ics", "pf", "phf", "coeval")
GIB = 1024**3


def load(label: str):
    d = RESULTS / label
    phases, steps = {}, defaultdict(list)
    with open(d / "summary_phases.csv") as f:
        for r in csv.DictReader(f):
            if r["status"] == "complete":
                key = (int(r["hii_dim"]), int(r["n_threads"]), int(r["coeval_batch"] or 0))
                phases[key + (r["phase"],)] = r
    p = d / "summary_coeval_steps.csv"
    if p.exists():
        with open(p) as f:
            for r in csv.DictReader(f):
                key = (int(r["hii_dim"]), int(r["n_threads"]), int(r["coeval_batch"] or 0))
                steps[key].append(r)
    return phases, steps


def fmt_t(s: float) -> str:
    return f"{s / 3600:.2f} h" if s >= 3600 else f"{s / 60:.1f} m" if s >= 60 else f"{s:.0f} s"


def main(a: str, b: str) -> None:
    pa, sa = load(a)
    pb, sb = load(b)
    configs = sorted({k[:3] for k in pa} & {k[:3] for k in pb})
    if not configs:
        sys.exit(f"no configuration completed in both {a} and {b}")
    print(f"A = {a}   B = {b}   (only phases complete in both)\n")
    print(f"{'HII_DIM':>7} {'NT':>3} {'CB':>3} {'phase':>6} {'wall A':>9} {'wall B':>9} {'B/A':>6} "
          f"{'peak A':>9} {'peak B':>9}")
    ics_extra = {}
    for c in configs:
        for ph in PHASES:
            ra, rb = pa.get(c + (ph,)), pb.get(c + (ph,))
            if not (ra and rb):
                continue
            wa, wb = float(ra["wall_s"]), float(rb["wall_s"])
            ma, mb = int(ra["peak_rss_bytes"]) / GIB, int(rb["peak_rss_bytes"]) / GIB
            print(f"{c[0]:7d} {c[1]:3d} {c[2]:3d} {ph:>6} {fmt_t(wa):>9} {fmt_t(wb):>9} {wb / wa:6.3f} "
                  f"{ma:7.1f} G {mb:7.1f} G")
            if ph == "ics" and c[2] == 0:
                ics_extra[c[:2]] = (wb - wa, wa)
        print()

    print("coeval steps (steady state = steps without process setup)")
    print(f"{'HII_DIM':>7} {'NT':>3} {'CB':>3} {'steps':>5} {'median B/A':>10} {'sum A':>9} {'sum B':>9} "
          f"{'1st step B-A':>12}")
    for c in configs:
        xa = {(r["batch"], r["index"]): r for r in sa.get(c, [])}
        xb = {(r["batch"], r["index"]): r for r in sb.get(c, [])}
        common = [k for k in xa if k in xb]
        steady = [k for k in common if xa[k]["includes_setup"] != "True" and xb[k]["includes_setup"] != "True"]
        if not steady:
            continue
        ratios = [float(xb[k]["wall_s"]) / float(xa[k]["wall_s"]) for k in steady]
        sum_a = sum(float(xa[k]["wall_s"]) for k in steady)
        sum_b = sum(float(xb[k]["wall_s"]) for k in steady)
        first = [k for k in common if xa[k]["includes_setup"] == "True" and xb[k]["includes_setup"] == "True"]
        d1 = sum(float(xb[k]["wall_s"]) - float(xa[k]["wall_s"]) for k in first)
        print(f"{c[0]:7d} {c[1]:3d} {c[2]:3d} {len(steady):5d} {statistics.median(ratios):10.3f} "
              f"{fmt_t(sum_a):>9} {fmt_t(sum_b):>9} {d1:+11.0f}s")

    print("\nICs-phase extra time with wisdom (B - A), ~ FFTW_PATIENT planning of DIM^3 r2c + c2r")
    for nt in sorted({k[1] for k in ics_extra}):
        pts = sorted((3 * dim, x, wa) for (dim, n), (x, wa) in ics_extra.items() if n == nt)
        for dim, x, wa in pts:
            print(f"  NT={nt:2d}  DIM={dim:5d}: {x:+8.0f} s  ({x / wa:+.0%} of the ICs phase without wisdom)")
        # fit only differences well above node-to-node noise
        good = [(d, x) for d, x, wa in pts if x > max(30.0, 0.1 * wa)]
        if len(good) < 2:
            print(f"  NT={nt:2d}  no clear planning cost (fewer than 2 sizes with B - A > max(30 s, 10%))")
        else:
            lx = [math.log(d) for d, _ in good]
            ly = [math.log(x) for _, x in good]
            mx, my = statistics.fmean(lx), statistics.fmean(ly)
            slope = sum((u - mx) * (v - my) for u, v in zip(lx, ly)) / sum((u - mx) ** 2 for u in lx)
            pred = math.exp(my + slope * (math.log(4500) - mx))
            print(f"  NT={nt:2d}  power law ~ DIM^{slope:.2f}  ->  DIM=4500: ~{fmt_t(pred)} "
                  f"(hires plans: ICs/PFs only, coevals skip them)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
