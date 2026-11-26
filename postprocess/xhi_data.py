"""The x_HI constraints of the reionisation-history figures: the observations and the Qin et al. (2025) band.

Shared by postprocess/plot_paper_lightcones.py (the x_HI panel of the global-history figure). The constants and
functions are those of postprocess/plot_xHI_history.ipynb (19 Nov 2026), which still has its own copies.
Data: postprocess/xHI_data/xHI_observations.csv (one row per constraint) and Qin25_xHI_band_digitized.txt.
"""
import csv
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent / "xHI_data"
OBS_FILE = DATA / "xHI_observations.csv"
QIN25_FILE = DATA / "Qin25_xHI_band_digitized.txt"
QIN25_COLOR = "#c8433f"
DATA_ALPHA = 0.45  # observations are for comparison: drawn faded
# method: (legend label, colour, filled markers)
METHODS = {
    "dark_pixels": ("Dark pixels", "#555555", True),
    "qso_dw": ("QSO damping wings", "#CC79A7", True),
    "gal_dw": ("Galaxy damping wings", "#CC79A7", False),
    "lya_ew": (r"Ly$\alpha$ EWs", "#56B4E9", True),
    "lae": ("LAE LF / clustering", "#8C6D31", True),
}
MARKERS = ["o", "s", "D", "^", "v", "<", ">", "p", "h", "*", "P", "X", "d", "8"]


def read_observations(path=OBS_FILE):
    """Rows of the observations CSV (comment lines start with #), numbers as floats."""
    with open(path) as f:
        rows = list(csv.DictReader(line for line in f if not line.startswith("#")))
    for r in rows:
        for k in ("z", "dz_lo", "dz_hi", "x", "dx_lo", "dx_hi"):
            r[k] = float(r[k])
        r["in_qin25"] = r["in_qin25"].strip() == "1"
    return rows


def dataset_markers(obs):
    """One marker per dataset within each method, in the order of the CSV."""
    style = {}
    for m in METHODS:
        for i, d in enumerate(dict.fromkeys(r["dataset"] for r in obs if r["method"] == m)):
            style[d] = MARKERS[i % len(MARKERS)]
    return style


def qin_band(path=QIN25_FILE):
    """The digitized Qin et al. (2025) band: z, lo95, lo68, hi68, hi95."""
    return dict(zip(["z", "lo95", "lo68", "hi68", "hi95"], np.loadtxt(path, unpack=True)))


def draw_point(ax, r, color, marker, filled, arrow=0.07, ms=4.5, z_errors=True, lw=0.9):
    """One constraint: value (with errors), range, or upper/lower limit (arrow, with the 1-sigma error on the limit if given)."""
    kw = dict(fmt=marker, ms=ms, color=color, mec=color, mfc=color if filled else "white", mew=lw,
              elinewidth=lw, capsize=1.8, capthick=lw, alpha=DATA_ALPHA, zorder=3)
    xerr = [[r["dz_lo"]], [r["dz_hi"]]] if z_errors and (r["dz_lo"] or r["dz_hi"]) else None
    if r["kind"] in ("value", "range"):
        ax.errorbar(r["z"], r["x"], yerr=[[r["dx_lo"]], [r["dx_hi"]]], xerr=xerr, **kw)
        return
    sign = -1 if r["kind"] == "upper" else 1
    yerr = [[0], [r["dx_hi"]]] if sign < 0 else [[r["dx_lo"]], [0]]
    ax.errorbar(r["z"], r["x"], yerr=yerr if max(yerr[0][0], yerr[1][0]) > 0 else None, xerr=xerr, **kw)
    ax.annotate("", xy=(r["z"], r["x"] + sign * arrow), xytext=(r["z"], r["x"]), zorder=3,
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=6, shrinkA=0, shrinkB=0,
                                alpha=DATA_ALPHA))


def draw_constraints(ax, ms=4.5, lw=0.9):
    """The Qin et al. (2025) band and all observations on an x_HI axis; returns the method legend handles."""
    from matplotlib.lines import Line2D

    q = qin_band()
    ax.fill_between(q["z"], q["lo95"], q["hi95"], color=QIN25_COLOR, alpha=0.25, lw=0, zorder=1)
    ax.fill_between(q["z"], q["lo68"], q["hi68"], color=QIN25_COLOR, alpha=0.6, lw=0, zorder=1)
    obs = read_observations()
    style = dataset_markers(obs)
    for r in obs:
        _, color, filled = METHODS[r["method"]]
        draw_point(ax, r, color, style[r["dataset"]], filled, ms=ms, lw=lw)
    return [Line2D([], [], ls="none", marker="o", ms=ms + 1, color=c, mec=c, mfc=c if f else "white", label=lab,
                   alpha=DATA_ALPHA) for lab, c, f in METHODS.values()]
