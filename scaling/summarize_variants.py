"""Table (and optional plot) of the scaling/bench_variant.py results.

    python3 scaling/summarize_variants.py
    python3 scaling/summarize_variants.py --plot plots/variants_history.png
    python3 scaling/summarize_variants.py --dir scaling/results/variants
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--dir", type=Path, default=Path(__file__).resolve().parent / "results" / "variants")
ap.add_argument("--plot", type=Path, default=None, help="PNG of x_HI(z) and T_b(z) of every variant")
args = ap.parse_args()

runs = [json.loads(p.read_text()) for p in sorted(args.dir.glob("*.json"))]
if not runs:
    raise SystemExit(f"no results in {args.dir}")


def z_at(z, x, level):
    """Redshift where x_HI crosses `level` (x_HI decreasing towards low z)."""
    z, x = np.asarray(z), np.asarray(x)
    o = np.argsort(z)
    z, x = z[o], x[o]
    above = np.nonzero(x >= level)[0]
    if not len(above) or above[0] == 0:
        return float("nan")
    i = above[0]
    return float(np.interp(level, [x[i - 1], x[i]], [z[i - 1], z[i]]))


GiB = 2**30
head = (f"{'variant':28s} {'cell':>4s} {'N':>4s} {'box':>5s} | {'ICs':>6s} {'PFs':>6s} {'halos':>6s} "
        f"{'coeval':>7s} {'/z':>5s} {'pc set-up':>9s} | {'peak':>6s} {'extra cache':>11s} | "
        f"{'z(0.5)':>6s} {'z(0.01)':>7s} {'tau':>6s}")
print(head)
print("-" * len(head))
for r in sorted(runs, key=lambda r: (r["cell_mpc"], r["hii_dim"], r["label"])):
    ph = r.get("phases", {})

    def m(name, ph=ph):
        return f"{ph[name]['wall_s'] / 60:6.1f}" if name in ph else f"{'-':>6s}"

    co = ph.get("coeval", {})
    steps = [s["s"] for s in co.get("steps", [])]
    per_z = f"{np.median(steps[1:]):5.0f}" if len(steps) > 2 else f"{'-':>5s}"
    setup = co.get("photoncons_setup_s")
    setup = f"{setup / 60:7.1f} m" if setup else f"{'-':>9s}"
    peak = max((p.get("peak_rss_bytes", 0) for p in ph.values()), default=0) / GiB
    extra = sum(v["bytes"] for k, v in r.get("cache_by_kind", {}).items()
                if k.startswith("other, written by this run"))
    h = r.get("history", {})
    z50 = z_at(h.get("redshift", []), h.get("x_HI", []), 0.5) if h.get("redshift") else float("nan")
    zend = z_at(h.get("redshift", []), h.get("x_HI", []), 0.01) if h.get("redshift") else float("nan")
    tau = h.get("tau_e", float("nan"))
    print(f"{r['label'][:28]:28s} {r['cell_mpc']:4.1f} {r['hii_dim']:4d} {r['box_len_mpc']:5.0f} | "
          f"{m('ics')} {m('pf')} {m('phf')} {(co.get('wall_s', 0) / 60):7.1f} {per_z} {setup} | "
          f"{peak:5.1f}G {extra / 1e9:9.2f}GB | {z50:6.2f} {zend:7.2f} {tau:6.4f}")
print("\nTimes in minutes (coeval '/z': median seconds per node redshift after the first; "
      "'pc set-up': photon-conservation calibration, part of the first coeval step). "
      "'extra cache': files this run wrote that are not node-redshift products (e.g. calibration boxes).")

if args.plot:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for r in runs:
        h = r.get("history", {})
        if not h.get("redshift"):
            continue
        lab = f"{r['label']} (N={r['hii_dim']})"
        ax[0].plot(h["redshift"], h["x_HI"], label=lab)
        ax[1].plot(h["redshift"], h["T_b_mK"], label=lab)
    ax[0].set(xlabel="z", ylabel=r"$\bar{x}_{\rm HI}$", xlim=(5, 15))
    ax[1].set(xlabel="z", ylabel=r"$\bar{T}_b$ [mK]", xlim=(5, 35))
    ax[0].legend(fontsize=7)
    args.plot.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.plot, dpi=150)
    print(f"plot: {args.plot}")
