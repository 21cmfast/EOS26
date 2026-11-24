"""Plot the reionization histories written by run_history.py: 21cmFAST 4.2 before and after the fix.

    python Mturn_bug/plot_history.py                 # results/*_HIIDIM200_*.json
    python Mturn_bug/plot_history.py --hii-dim 86

Left: box-mean neutral fraction with the Qin et al. (2025) points. Right: box mean of
log10 of the ACG turnover mass used for the halo emissivities. Writes
Mturn_bug/Mturn_bug_xHI.png and .pdf and prints the redshifts of a few x_HI levels.
Needs numpy and matplotlib only.
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
plt.rcParams.update({
    "font.family": "serif",
    "mathtext.fontset": "dejavuserif",
    "font.size": 18,
    "axes.labelsize": 20,
    "xtick.labelsize": 17,
    "ytick.labelsize": 17,
    "legend.fontsize": 15,
})

# Qin et al. (2025) x_HI(z) points, as in postprocess/plot_all_summaries.ipynb
QIN25_Z = [5.44, 6.35, 6.75, 7.17, 7.7, 8.2, 8.5, 8.85, 9.18, 9.65, 10.01, 10.19, 10.30, 10.87, 11.88, 12.30, 13.144, 14.30]
QIN25_XHI = [0.01, 0.2, 0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.84, 0.85, 0.86, 0.9, 0.94, 0.952, 0.96947, 0.9822]
# label -> (legend text, colour, line style); other labels are drawn with their own name
STYLE = {
    "v4.2": ("21cmFAST 4.2", "C1", "-"),
    "v4.2fix": ("21cmFAST 4.2 with the fix of PR #737", "C1", "--"),
    "v4.3": ("21cmFAST {version}", "C0", "-"),
}
LEVELS = [0.9, 0.75, 0.5, 0.25, 0.1, 0.05]

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--hii-dim", type=int, default=200)
ap.add_argument("--results", type=Path, default=HERE / "results")
ap.add_argument("--out", type=Path, default=HERE / "Mturn_bug_xHI")
ap.add_argument("--no-qin25", action="store_true", help="leave out the Qin+25 points")
args = ap.parse_args()


def z_at(z, x, level):
    """Redshift at which x_HI first drops below level, coming from high redshift."""
    o = np.argsort(z)[::-1]
    zz, xx = np.asarray(z)[o], np.asarray(x)[o]
    i = np.nonzero(xx <= level)[0]
    if len(i) == 0 or i[0] == 0:
        return np.nan
    i = i[0]
    return float(np.interp(level, [xx[i], xx[i - 1]], [zz[i], zz[i - 1]]))


runs = []
for fn in sorted(args.results.glob(f"*_HIIDIM{args.hii_dim}_*.json")):
    d = json.load(open(fn))
    rows = sorted(d["rows"], key=lambda r: r["z"])
    z = np.array([r["z"] for r in rows])
    runs.append(dict(d, file=fn.name, z=z,
                     xHI=np.array([r["xHI"] for r in rows]),
                     mturn=np.array([r["log10_mturn_acg"] for r in rows])))
if not runs:
    raise SystemExit(f"no results/*_HIIDIM{args.hii_dim}_*.json")
order = {k: i for i, k in enumerate(STYLE)}
runs.sort(key=lambda r: order.get(r["label"], len(order)))

fig, ax = plt.subplots(1, 2, figsize=(15, 6))
if not args.no_qin25:
    ax[0].scatter(QIN25_Z, QIN25_XHI, color="k", s=30, zorder=5, label="Qin et al. (2025)")
for r in runs:
    text, colour, ls = STYLE.get(r["label"], (r["label"], None, "-"))
    text = text.format(version=r["version"])
    ax[0].plot(r["z"], r["xHI"], color=colour, ls=ls, lw=2.5, label=text)
    ax[1].plot(r["z"], r["mturn"], color=colour, ls=ls, lw=2.5, label=text)
ax[0].set_xlim(5, 16)
ax[0].set_ylim(0, 1.02)
ax[0].set_xlabel("Redshift")
ax[0].set_ylabel(r"$\overline{x}_{\rm HI}$")
ax[0].legend(handles=ax[0].collections, frameon=False, loc="lower right")
ax[1].set_xlim(5, 20)
lo, hi = ax[1].get_ylim()
ax[1].set_ylim(lo, hi + 0.25 * (hi - lo))
ax[1].legend(frameon=False, loc="upper right")
ax[1].set_xlabel("Redshift")
ax[1].set_ylabel(r"$\langle \log_{10}(M_{\rm turn,ACG}/M_\odot) \rangle$")
for a in ax:
    a.tick_params(direction="in", which="both", top=True, right=True)
plt.tight_layout()
for ext in ("png", "pdf"):
    plt.savefig(args.out.with_suffix(f".{ext}"), dpi=200, bbox_inches="tight")
print("saved", args.out.with_suffix(".png"), "and .pdf")

r0 = runs[0]
print(f"HII_DIM = {r0['HII_DIM']}, BOX_LEN = {r0['BOX_LEN']} cMpc")
print(f"{'':46s}" + "".join(f"{'x=' + str(l):>8s}" for l in LEVELS))
if not args.no_qin25:
    print(f"{'Qin+25':46s}" + "".join(f"{np.interp(l, QIN25_XHI, QIN25_Z):8.2f}" for l in LEVELS))
for r in runs:
    name = f"{r['label']} ({r['version']}, N_THREADS={r['N_THREADS']})"
    print(f"{name:46s}" + "".join(f"{z_at(r['z'], r['xHI'], l):8.2f}" for l in LEVELS))
