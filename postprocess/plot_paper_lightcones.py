"""Paper figures of the EOS26 lightcones: the angular plane as a to-scale arc, and lightcone bands.

    EOS26_TEMPLATE=EOS26_earlyEoR python postprocess/plot_paper_lightcones.py arc
    EOS26_TEMPLATE=EOS26_earlyEoR python postprocess/plot_paper_lightcones.py bands
    python postprocess/plot_paper_lightcones.py arc --quantities density neutral_fraction --width 90

arc    The angular plane (the lightcone on the equator of the observer at the box centre),
       drawn to scale: the distance from the observer is the comoving distance, from z = 5
       (7.95 cGpc) to z = 35 (11.78 cGpc), and the angle on the page is the longitude. The
       --width degrees around longitude 0 (the centre of the HEALPix patch) are split into one
       sector per quantity. Input: <lightcone dir>/angular_plane/<quantity>.h5.
       Output: plots/arc_<run>.{png,pdf}.
bands  One plane of the rectilinear lightcone of each quantity (box cells x = 0, the first
       --band-width cMpc in y), z = 5-35 from left to right. Input: rect/<quantity> of
       <lightcone dir>/figure_data.h5 (postprocess/export_figure_data.py).
       Output: plots/bands_<run>.{png,pdf}.
global One column: the 21-cm power at k = 0.1/cMpc (power_spectra/ of postprocess/power_spectra.py),
       the mean 21-cm brightness temperature, the neutral fraction, and the kinetic and spin
       temperatures, vs z, of both EOS26 runs (fiducial and early EoR; see eos26_runs for where the
       fiducial curves come from until its lightcones exist), EOS21 (plots/EOS21) and EOS16
       (plots/EOS16, 1024^3 runs). Means are box means at the node redshifts (global_mean of the
       angular-plane stores); bands the 16-84 and 2.5-97.5 percentiles of the angular-plane cells.
       Reads the runs' lightcone directories (not --dir). Output: plots/global_<run>.{png,pdf}.

<lightcone dir> is --dir, else that of the run of $EOS26_TEMPLATE (postprocess/lightcone): on the
laptop <cache>/lightcones, e.g. EOS26_earlyEoR_cache/lightcones. Each image pixel is the mean of
the lightcone samples that fall in it (empty pixels: the nearest sample).
"""
import argparse
import sys
import time
from pathlib import Path

import h5py
import numpy as np
from matplotlib import colormaps, colors

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "run_scripts").is_dir())
NU21 = 1420.405751768  # MHz
RSD = "brightness_temp_dvdr_with_rsds"
SECONDS_PER_YEAR = 3.15576e7
KM_PER_MPC = 3.0856776e19


def physical(q, values, z):
    """los_velocity in km/s: 21cmFAST stores (1 + z) times the peculiar velocity, in Mpc/s (the RSD
    displacement is v / H); the other quantities as they are. z: the redshift of the last axis."""
    if q != "los_velocity":
        return values
    return values * KM_PER_MPC / (1 + np.asarray(z))

# quantity: (name, colour-bar label, colour map, scale, limits, factor). Scales: lin, log (log10 of
# the values; values below the lower limit get its colour), log1p (log10(1 + x)). The factor
# converts the stored values to the units of the label.
SPEC = {
    "density": ("Density", r"$\log_{10}(1+\delta)$", "magma", "log1p", (-0.45, 0.45), 1),
    "los_velocity": ("Line-of-sight velocity", r"$v_\parallel$ [km s$^{-1}$]", "RdBu_r", "lin", (-400, 400), 1),
    "sfrd_acg": ("Star formation (ACGs)", r"$\log_{10}\,\dot\rho_\ast$ [$M_\odot$ yr$^{-1}$ cMpc$^{-3}$]",
                 "afmhot", "log", (-4, 0), SECONDS_PER_YEAR),
    "sfrd_mcg": ("Star formation (MCGs)", r"$\log_{10}\,\dot\rho_{\ast,\rm MCG}$ [$M_\odot$ yr$^{-1}$ cMpc$^{-3}$]",
                 "afmhot", "log", (-6, -2.5), SECONDS_PER_YEAR),
    # n_ion: ionising photons emitted into the IGM per baryon (21cmFAST: f_esc N_gamma M_* / (rho_crit Omega_b));
    # xray_emissivity: soft-band (< 2 keV) X-ray emissivity in units of 1e38 erg/s/cMpc^3
    "n_ion": ("Ionising photons", r"$\log_{10} N_{\rm ion}$ [per baryon]", "viridis", "log", (-2.5, 1.5), 1),
    "xray_emissivity": ("X-ray emissivity", r"$\log_{10}\,\epsilon_{\rm X}$ [$10^{38}$ erg s$^{-1}$ cMpc$^{-3}$]",
                        "inferno", "log", (-2, 2), 1),
    "J_21_LW": ("Lyman–Werner background", r"$\log_{10} J_{\rm LW,21}$", "Blues_r", "log", (-2, 1.5), 1),
    "ionisation_rate_G12": ("Photoionisation rate", r"$\log_{10}\,\Gamma_{12}$", "cividis", "log", (-2, 0.5), 1),
    "kinetic_temp_neutral": ("Gas temperature", r"$\log_{10} T_{\rm K}$ [K]", "inferno", "log", (0.7, 3.4), 1),
    "spin_temperature": ("Spin temperature", r"$\log_{10} T_{\rm S}$ [K]", "plasma", "log", (0.7, 3.4), 1),
    "neutral_fraction": ("Neutral fraction", r"$x_{\rm HI}$", "gray", "lin", (0, 1), 1),
    "cumulative_recombinations": ("Recombinations", r"$N_{\rm rec}$", "Reds_r", "lin", (0, 3), 1),
    "brightness_temp": ("21-cm signal, no velocity terms", r"$\delta T_{\rm b}$ [mK]", "EoR", "lin", (-150, 30), 1),
    RSD: ("21-cm signal", r"$\delta T_{\rm b}$ [mK]", "EoR", "lin", (-150, 30), 1),
}
# names under the arc's sectors, with the units of the tick labels of the colour bars above them (log quantities are labelled
# with their values, not their logarithms)
ARC_NAME = {"density": "Density\n" r"$1+\delta$", "sfrd_acg": "Star formation\n" r"[$M_\odot$ yr$^{-1}$ cMpc$^{-3}$]",
            "J_21_LW": "Lyman–Werner\n" r"$J_{\rm LW,21}$", "kinetic_temp_neutral": "Gas temperature\n[K]",
            "spin_temperature": "Spin temperature\n[K]", RSD: "21-cm signal\n[mK]", "brightness_temp": "21-cm signal\n[mK]",
            "neutral_fraction": "Neutral fraction"}
ARC = ["density", "sfrd_acg", "J_21_LW", "kinetic_temp_neutral", RSD, "neutral_fraction"]
BANDS = ["density", "los_velocity", "sfrd_acg", "sfrd_mcg", "n_ion", "xray_emissivity", "J_21_LW",
         "ionisation_rate_G12", "kinetic_temp_neutral", "spin_temperature", "neutral_fraction",
         "cumulative_recombinations", "brightness_temp", RSD]


def eor_colormap(vmin, vmax):
    """tuesday's eor_colormap: white-yellow-orange-maroon for absorption, black at 0, blue for emission."""
    zero = min(max(-vmin / (vmax - vmin), 0.0), 1.0)
    cols = [(zero * i / 4, c) for i, c in enumerate(["white", "yellow", "orange", "maroon"])] + [(zero, "black")]
    cols += [(zero + (1 - zero) * (i + 1) / 2, c) for i, c in enumerate(["#1f77b4", "skyblue"])]
    return colors.LinearSegmentedColormap.from_list("EoR", cols)


def colour_scale(q, values=None):
    """(cmap, norm, transform) of q; limits from the 1st and 99.5th percentiles if SPEC has none."""
    _, _, cmap, scale, lim, factor = SPEC[q]

    def transform(v):
        v = np.asarray(v, dtype=np.float64) * factor
        if scale == "log":
            return np.log10(np.where(v > 0, v, np.nan))
        if scale == "log1p":
            return np.log10(np.clip(1 + v, 1e-3, None))
        return v

    if lim is None:
        t = transform(values)
        lim = tuple(np.nanpercentile(t[np.isfinite(t)], [1, 99.5]))
    cm = eor_colormap(*lim) if cmap == "EoR" else colormaps[cmap]
    cm = cm.with_extremes(bad=cm(0.0))  # zeros of log quantities: the lowest colour
    return cm, colors.Normalize(*lim), transform


def rgb(q, values, scale=None):
    cm, norm, transform = scale or colour_scale(q, values)
    return cm(norm(transform(values)))[..., :3]


def style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # STIX: the Times-like font of A&A's text (as Fig. 1, plot_fov_zoom.py)
    plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 9,
                         "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6})
    return plt


def lightcone_dir(args):
    if args.dir:
        return Path(args.dir)
    sys.path.insert(1, str(REPO / "run_scripts"))
    sys.path.insert(1, str(REPO / "postprocess" / "lightcone"))
    import eos_lightcones as el
    import settings

    return el.default_out_dir(settings.inputs_for_run(False, False)[0])


def store(directory, q):
    """The open angular-plane store of q (brightness_temp if finalise has not made RSD yet)."""
    for name in (q, "brightness_temp") if q == RSD else (q,):
        p = directory / f"{name}.h5"
        if p.exists():
            h = h5py.File(p, "r")
            if h.attrs.get("complete", False):
                if name != q:
                    print(f"{q}: not made yet, showing {name}")
                return h
            h.close()
    sys.exit(f"no complete {q}.h5 in {directory}")


# ====================================================================== the arc
def arc(args):
    plt = style()
    t0 = time.time()
    src = lightcone_dir(args) / "angular_plane"
    qs = args.quantities or ARC
    n = len(qs)
    edges = np.linspace(-args.width / 2, args.width / 2, n + 1)  # longitudes [deg], left to right

    with store(src, qs[0]) as h:
        dist = h["lightcone_distances"][:] / 1e3  # cGpc
        zs = h["lightcone_redshifts"][:]
        n_lon = h["lightcone"].shape[0]
    keep = (zs >= args.zmin) & (zs <= args.zmax)
    k0, k1 = np.flatnonzero(keep)[[0, -1]]
    k1 += 1
    d = dist[k0:k1]
    r_in, r_out = d[0], d[-1]
    z_of_r = lambda r: np.interp(r, dist, zs)  # noqa: E731
    r_of_z = lambda z: np.interp(z, zs, dist)  # noqa: E731

    # page: x to the right, y up, observer at (0, 0), longitude 0 straight up, cGpc
    half = np.radians(args.width / 2)
    rb0, rb1 = r_out + 0.12, r_out + 0.32  # the curved colour bars, just above the sectors
    x_max = (rb1 + 0.4) * np.sin(half) + 0.5  # room for the tick labels
    y_lo, y_hi = r_in * np.cos(half) - 0.8, rb1 + 0.5
    nx = args.pixels
    px = 2 * x_max / nx
    ny = int(np.ceil((y_hi - y_lo) / px))
    img = np.ones((ny, nx, 3))
    # the (distance, longitude) of each pixel
    X = (np.arange(nx) + 0.5) * px - x_max
    Y = y_hi - (np.arange(ny) + 0.5) * px
    R = np.hypot(X[None, :], Y[:, None]).ravel()
    TH = np.degrees(np.arctan2(X[None, :], Y[:, None])).ravel()
    inside = (R >= r_in) & (R <= r_out)
    # page angle (clockwise from up) = minus the longitude: east to the left, as on the sky maps
    lon = -((np.arange(n_lon) * 360 / n_lon + 180) % 360 - 180)
    scales = []
    for i, q in enumerate(qs):
        rows = np.flatnonzero((lon >= edges[i]) & (lon < edges[i + 1]))
        with store(src, q) as h:  # read as contiguous runs of rows
            ds = h["lightcone"]
            runs = np.split(rows, np.flatnonzero(np.diff(rows) != 1) + 1)
            block = np.concatenate([ds[r[0]:r[-1] + 1, k0:k1] for r in runs]).astype(np.float64)
        order = np.argsort(lon[rows])
        block, lon_s = physical(q, block[order], zs[k0:k1]), lon[rows][order]
        # mean of the samples in each pixel
        th = np.radians(lon_s)[:, None]
        ix = ((d[None, :] * np.sin(th) + x_max) / px).astype(np.int64)
        iy = ((y_hi - d[None, :] * np.cos(th)) / px).astype(np.int64)
        flat = (iy * nx + ix).ravel()
        sel = inside & (TH >= edges[i]) & (TH < edges[i + 1])
        tot = np.bincount(flat, weights=block.ravel(), minlength=nx * ny)[sel]
        cnt = np.bincount(flat, minlength=nx * ny)[sel]
        del flat, ix, iy
        vals = np.where(cnt > 0, tot / np.maximum(cnt, 1), np.nan)
        empty = cnt == 0
        if empty.any():  # the nearest sample
            ia = np.clip(np.searchsorted(lon_s, TH[sel][empty]), 0, lon_s.size - 1)
            ib = np.clip(np.searchsorted(d, R[sel][empty]), 0, d.size - 1)
            vals[empty] = block[ia, ib]
        sc = colour_scale(q, block[:, ::7])
        scales.append(sc)
        img.reshape(-1, 3)[sel] = rgb(q, vals, sc)
        print(f"{q}: {rows.size} longitudes x {d.size} slices, {empty.mean():.1%} empty pixels "
              f"({time.time() - t0:.0f} s)")
    del R, TH, inside

    # ------------------------------------------------------------------ figure
    W = args.fig_width
    ax_h = W * (y_hi - y_lo) / (2 * x_max)
    # the full sky and the patch below, if export_figure_data.py's file is there
    fd = lightcone_dir(args) / "figure_data.h5"
    sky = None
    if args.sky and fd.exists():
        sky = h5py.File(fd, "r")
        if f"healpix/{args.sky_quantity}" not in sky:
            print(f"{fd.name} has no healpix/{args.sky_quantity}; no sky maps")
            sky.close()
            sky = None
    elif args.sky:
        print(f"no {fd}: no sky maps")
    sky_in = (args.fig_width - 1.5) / 3  # height of the sky maps (Mollweide 2:1, square zoom)
    sky_h = sky_in + 0.85 if sky is not None else 0
    H = ax_h + sky_h
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0, 1 - ax_h / H, 1, ax_h / H])
    ax.imshow(img, extent=[-x_max, x_max, y_lo, y_hi], interpolation="nearest", origin="upper",
              rasterized=True)
    ax.set_xlim(-x_max, x_max)
    ax.set_ylim(y_lo, y_hi)
    ax.set_aspect("equal")
    ax.axis("off")
    t = np.radians(np.linspace(-args.width / 2, args.width / 2, 400))
    for e in np.radians(edges):  # sector edges
        ax.plot([r_in * np.sin(e), r_out * np.sin(e)], [r_in * np.cos(e), r_out * np.cos(e)], color="w", lw=0.8)
    for r in (r_in, r_out):
        ax.plot(r * np.sin(t), r * np.cos(t), color="k", lw=0.6)
    for z in args.z_arcs:  # faint arcs of constant redshift
        r = r_of_z(z)
        ax.plot(r * np.sin(t), r * np.cos(t), color="w", lw=0.4, alpha=0.6, ls=(0, (4, 3)))
    for e in np.radians(edges[[0, -1]]):
        ax.plot([r_in * np.sin(e), r_out * np.sin(e)], [r_in * np.cos(e), r_out * np.cos(e)], color="k", lw=0.6)

    def edge_ticks(a_deg, side, ticks, title):
        """Ticks on the left (side -1) or right (+1) edge: (radius, label) pairs; title along the edge."""
        a = np.radians(a_deg)
        nrm = side * np.array([np.cos(a), -np.sin(a)])  # outward normal
        for r, lab in ticks:
            p = np.array([r * np.sin(a), r * np.cos(a)])
            ax.plot(*np.c_[p, p + 0.12 * nrm], color="k", lw=0.6)
            ax.text(*(p + 0.2 * nrm), lab, ha="right" if side < 0 else "left", va="center", fontsize=FS["tick"])
        rm = 0.5 * (r_in + r_out)
        p = np.array([rm * np.sin(a), rm * np.cos(a)]) + 0.75 * nrm
        ax.text(*p, title, ha="center", va="center", rotation=90 - a_deg - (180 if side < 0 else 0), fontsize=FS["title"])

    edge_ticks(edges[0], -1, [(r_of_z(z), f"{z:g}") for z in (5, 6, 8, 10, 15, 20, 35)], "Redshift")
    edge_ticks(edges[-1], 1, [(r_of_z(NU21 / nu - 1), f"{nu}") for nu in (50, 100, 150, 200)],
               "Frequency [MHz]")
    # each sector: a curved colour bar above it (tick labels on top) and its name under it
    pt = (2 * x_max) / (W * 72)  # one point in page units (cGpc)
    # the largest name size (at most FS["name"]) at which every name fits under its sector, 1 deg to spare
    names = [ARC_NAME.get(q, SPEC[q][0]).split("\n") for q in qs]
    room = np.radians(edges[1] - edges[0] - 1) * (r_in - 0.1 - 1.25 * pt * FS["name"])
    size = FS["name"]
    while size > 6 and max(token_widths(ax, nm[0], size)[1].sum() for nm in names) > room:
        size -= 0.25
    print(f"names at {size:g} pt")
    for i, (q, (cm, norm, _)) in enumerate(zip(qs, scales)):
        m = np.radians(0.5 * (edges[i] + edges[i + 1]))
        for k, line in enumerate(names[i]):  # name, then units, along the inner edge
            curved_text(ax, line, r_in - 0.1 - (k + 0.8) * 1.25 * pt * size, np.degrees(m), size - (1 if k else 0))
        curved_colour_bar(ax, q, cm, norm, edges[i] + 2, edges[i + 1] - 2, rb0, rb1)
    # inside: the box size, and the way to the observer
    yc = r_in * np.cos(half) + 0.45
    L = args.box / 1e3
    ax.plot([-L / 2, L / 2], [yc, yc], color="k", lw=1.2, solid_capstyle="butt")
    ax.text(0, yc + 0.15, f"Box size, {L:g} cGpc", ha="center", va="bottom", fontsize=FS["note"])
    ax.annotate("", xy=(0, y_lo + 0.02), xytext=(0, yc - 0.12), arrowprops=dict(arrowstyle="->", lw=0.6))
    ax.text(0.1, 0.5 * (y_lo + yc - 0.12), f"Observer at {r_in:.2f} cGpc", fontsize=FS["note"], ha="left", va="center")

    if sky is not None:
        sky_row(fig, plt, sky, args, y_top=(H - ax_h) / H, height=sky_h / H)
    out = Path(args.out) if args.out else REPO / "plots" / f"arc_{args.run}"
    for ext in ("png", "pdf"):
        fig.savefig(out.with_suffix(f".{ext}"), dpi=args.dpi)
    print(f"wrote {out}.png/.pdf ({time.time() - t0:.0f} s)")


LIN_TICKS = {"neutral_fraction": [0, 0.5, 1], RSD: [-150, -100, -50, 0], "brightness_temp": [-150, -100, -50, 0],
             "cumulative_recombinations": [0, 1, 2, 3], "los_velocity": [-400, 0, 400]}


def ticks(q, norm):
    """Tick positions (in the units of the colour scale) and labels: values, also for log scales."""
    lo, hi = norm.vmin, norm.vmax
    scale = SPEC[q][3]
    if scale == "log":  # whole powers of ten, at most four
        e = np.arange(np.ceil(lo - 1e-9), np.floor(hi + 1e-9) + 1)
        e = e[:: int(np.ceil(e.size / 4))]
        lab = {0: "1", 1: "10"}
        return e, [lab.get(int(k), f"$10^{{{int(k)}}}$") for k in e]
    if scale == "log1p":
        v = np.array([v for v in (0.3, 0.5, 1, 2, 3, 5) if lo <= np.log10(v) <= hi])
        return np.log10(v), [f"{x:g}" for x in v]
    from matplotlib.ticker import MaxNLocator

    t = LIN_TICKS.get(q) or MaxNLocator(4).tick_values(lo, hi)
    t = [x for x in t if lo - 1e-9 <= x <= hi + 1e-9]
    return np.array(t), [f"{x:g}".replace("-", "−") for x in t]


FS = {"tick": 9.5, "title": 11, "name": 10, "note": 10, "cbar": 9}  # arc font sizes [pt]; names: at most


def token_widths(ax, s, size):
    """The characters (and $...$ groups) of s and their widths in page units at a font size."""
    import re

    from matplotlib.font_manager import FontProperties

    renderer = ax.figure.canvas.get_renderer()
    prop = FontProperties(family="STIXGeneral", size=size)
    per_px = (ax.transData.inverted().transform((1, 0)) - ax.transData.inverted().transform((0, 0)))[0]
    tokens = re.findall(r"\$[^$]*\$|.", s)
    w = np.array([renderer.get_text_width_height_descent(t, prop, ismath=t.startswith("$"))[0] for t in tokens])
    return tokens, w * per_px


def curved_text(ax, s, r, a_mid, size):
    """s along the arc of radius r (page units), centred on the page angle a_mid (degrees clockwise from up),
    baseline on the arc, reading left to right. Each character (or $...$ group) is placed on its own."""
    tokens, w = token_widths(ax, s, size)
    centres = np.cumsum(w) - w / 2 - w.sum() / 2  # arc length of each token's centre
    for t, c in zip(tokens, centres):
        a = np.radians(a_mid) + c / r
        ax.text(r * np.sin(a), r * np.cos(a), t, ha="center", va="baseline", rotation=-np.degrees(a),
                rotation_mode="anchor", fontsize=size)


def curved_colour_bar(ax, q, cm, norm, a0, a1, r0, r1, n=256):
    """A colour bar along an arc of the page (angles a0 < a1 in degrees, clockwise from up; radii r0 < r1),
    values increasing clockwise, with ticks and labels on its outer side."""
    a = np.radians(np.linspace(a0, a1, n + 1))
    r = np.array([r0, r1])
    X, Y = r[:, None] * np.sin(a)[None, :], r[:, None] * np.cos(a)[None, :]
    v = np.linspace(norm.vmin, norm.vmax, n)
    ax.pcolormesh(X, Y, v[None, :], cmap=cm, norm=norm, shading="flat", rasterized=True)
    for rr in r:
        ax.plot(rr * np.sin(a), rr * np.cos(a), color="k", lw=0.4)
    for aa in a[[0, -1]]:
        ax.plot(r * np.sin(aa), r * np.cos(aa), color="k", lw=0.4)
    for t, lab in zip(*ticks(q, norm)):
        aa = np.radians(a0 + (t - norm.vmin) / (norm.vmax - norm.vmin) * (a1 - a0))
        ax.plot([r1 * np.sin(aa), (r1 + 0.07) * np.sin(aa)], [r1 * np.cos(aa), (r1 + 0.07) * np.cos(aa)],
                color="k", lw=0.4)
        rl = r1 + 0.1
        ax.text(rl * np.sin(aa), rl * np.cos(aa), lab, ha="center", va="bottom", rotation=-np.degrees(aa),
                rotation_mode="anchor", fontsize=FS["cbar"])


def sky_row(fig, plt, f, args, y_top, height):
    """Full sky (Mollweide, Nside 1024) and the centre of the patch (gnomonic, Nside 4096) of one
    quantity at the slice nearest to --sky-z, with the angular plane (the equator) marked."""
    import healpy as hp

    q = args.sky_quantity
    zsl = f["slice_redshift"][:]
    i = int(np.argmin(np.abs(zsl - args.sky_z)))
    z = zsl[i]
    full = f[f"healpix/{q}"][i].astype(np.float64)
    patch, pix = f[f"patch/{q}"][i].astype(np.float64), f["patch/pixels"][:]
    nside_p = int(f.attrs["patch_nside"])
    cm, norm, transform = colour_scale(q, full)
    W = fig.get_figwidth()
    Hf = fig.get_figheight()
    h_in = height * Hf - 0.85  # the maps' height; the rest for the titles and labels
    # Mollweide
    mw = hp.projector.MollweideProj(xsize=1600)
    img = mw.projmap(full, lambda x, y, zz: hp.vec2pix(hp.npix2nside(full.size), x, y, zz))
    w_m = 2 * h_in
    y0 = y_top - (h_in + 0.35) / Hf
    axm = fig.add_axes([0.03, y0, w_m / W, h_in / Hf])
    axm.imshow(transform(np.where(np.isfinite(img) & (img > -1e30), img, np.nan)), cmap=cm.with_extremes(bad="none"),
               norm=norm,
               origin="lower", extent=[-2, 2, -1, 1], interpolation="nearest", rasterized=True)
    axm.set_xlim(-2.02, 2.02)
    axm.set_ylim(-1.01, 1.01)
    axm.axis("off")
    # the equator = the angular plane; the arc's longitudes in bold; the patch outline
    lon = np.linspace(-180, 180, 721)
    x, y = mw.ang2xy(lon, np.zeros_like(lon), lonlat=True)
    axm.plot(x, y, color="w", lw=0.5, alpha=0.8)
    lw_ = np.linspace(-args.width / 2, args.width / 2, 200)
    x, y = mw.ang2xy(lw_, np.zeros_like(lw_), lonlat=True)
    axm.plot(x, y, color="#ffd54f", lw=1.6)
    t = np.linspace(0, 2 * np.pi, 400)
    R = np.radians(45)
    vx, vy, vz = np.full_like(t, np.cos(R)), np.sin(R) * np.cos(t), np.sin(R) * np.sin(t)  # circle of 45 deg around (1, 0, 0)
    th, ph = hp.vec2ang(np.c_[vx, vy, vz])
    x, y = mw.ang2xy(th, ph)
    axm.plot(x, y, color="w", lw=0.6, ls="--")
    axm.text(0, -1.08, f"full sky, $N_{{\\rm side}}={hp.npix2nside(full.size)}$, $z={z:.2f}$", ha="center",
             va="top", fontsize=8.5)
    # gnomonic zoom on the patch centre
    side = args.sky_zoom  # deg
    npx = 900
    gx = np.linspace(-side / 2, side / 2, npx)
    GX, GY = np.meshgrid(np.radians(gx), np.radians(gx))
    vec = np.stack([np.ones_like(GX), GX, GY], axis=-1)  # tangent plane at (lon, lat) = (0, 0)
    ip = hp.vec2pix(nside_p, vec[..., 0], vec[..., 1], vec[..., 2])
    j = np.clip(np.searchsorted(pix, ip), 0, pix.size - 1)
    zoom = np.where(pix[j] == ip, patch[j], np.nan)
    axz = fig.add_axes([0.03 + (w_m + 0.55) / W, y0, h_in / W, h_in / Hf])
    axz.imshow(transform(zoom), cmap=cm, norm=norm, origin="lower", extent=[side / 2, -side / 2, -side / 2, side / 2],
               interpolation="nearest", rasterized=True)
    axz.axhline(0, color="#ffd54f", lw=1.0)
    axz.set_xlabel("longitude [deg]", fontsize=8.5, labelpad=1)
    axz.set_ylabel("latitude [deg]", fontsize=8.5, labelpad=1)
    axz.tick_params(labelsize=7.5, length=2)
    axz.text(0.5, 1.02, f"patch centre, $N_{{\\rm side}}={nside_p}$", transform=axz.transAxes, ha="center",
             va="bottom", fontsize=8.5)
    # where the zoom is on the full sky
    s = side / 2
    bx = np.r_[-s, s, s, -s, -s]
    by = np.r_[-s, -s, s, s, -s]
    x, y = mw.ang2xy(bx, by, lonlat=True)
    axm.plot(x, y, color="r", lw=0.8)
    cax = fig.add_axes([0.03 + (w_m + 0.55 + h_in + 0.12) / W, y0, 0.1 / W, h_in / Hf])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cm), cax=cax)
    cb.ax.tick_params(labelsize=7.5, length=2)
    cb.set_label(SPEC[q][1], fontsize=8.5, rotation=90, labelpad=3)
    f.close()


# ====================================================================== the bands
def bands(args):
    plt = style()
    path = lightcone_dir(args) / "figure_data.h5"
    if not path.exists():
        sys.exit(f"no {path}: run postprocess/export_figure_data.py on Gadi and copy its output here")
    with h5py.File(path, "r") as f:
        dist = f["lightcone_distances"][:] / 1e3  # cGpc
        zs = f["lightcone_redshifts"][:]
        qs = [q for q in (args.quantities or BANDS) if f"rect/{q}" in f]
        missing = [q for q in (args.quantities or BANDS) if f"rect/{q}" not in f]
        if missing:
            print(f"not in {path.name}: {missing}")
        n_cells = int(round(args.band_width / args.cell))
        data = {q: physical(q, f[f"rect/{q}"][:n_cells], zs) for q in qs}
    keep = (zs >= args.zmin) & (zs <= args.zmax)
    d = dist[keep]
    n = len(qs)
    W = args.fig_width
    left, right, cbw = 0.08, 0.92, 0.012  # axes span, colour-bar width (figure fractions)
    band_h = W * (right - left) * (args.band_width / 1e3) / (d[-1] - d[0])  # to scale, inches
    gap, top, bottom = 0.05, 0.45, 0.45
    H = top + bottom + n * band_h + (n - 1) * gap
    fig = plt.figure(figsize=(W, H))
    for i, q in enumerate(qs):
        y0 = 1 - (top + (i + 1) * band_h + i * gap) / H
        ax = fig.add_axes([left, y0, right - left, band_h / H])
        cm, norm, transform = colour_scale(q, data[q][:, keep])
        ax.imshow(transform(data[q][:, keep]), extent=[d[0], d[-1], 0, args.band_width], origin="lower",
                  cmap=cm, norm=norm, aspect="auto", interpolation="nearest", rasterized=True)
        ax.set_yticks([])
        ax.text(0.004, 0.9, SPEC[q][0], transform=ax.transAxes, ha="left", va="top", fontsize=8,
                bbox=dict(fc="w", ec="none", alpha=0.8, pad=1.2))
        cax = fig.add_axes([right + 0.006, y0, cbw, band_h / H])
        cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cm), cax=cax)
        cb.ax.tick_params(labelsize=6.5, length=1.5, pad=1)
        cb.outline.set_linewidth(0.4)
        cb.locator = plt.MaxNLocator(3)
        cb.update_ticks()
        cax.text(3.2, 0.5, SPEC[q][1], transform=cax.transAxes, rotation=90, ha="left", va="center", fontsize=6.5)
        zt = [z for z in (5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 35) if d[0] <= np.interp(z, zs, dist) <= d[-1]]
        ax.set_xticks(np.interp(zt, zs, dist))
        ax.set_xticklabels([f"{z:g}" for z in zt] if i == n - 1 else [])
        if i == 0:
            top_ax = ax.secondary_xaxis("top", functions=(lambda x: x, lambda x: x))
            nus = [nu for nu in (50, 60, 75, 100, 125, 150, 200) if d[0] <= np.interp(NU21 / nu - 1, zs, dist) <= d[-1]]
            top_ax.set_xticks(np.interp([NU21 / nu - 1 for nu in nus], zs, dist))
            top_ax.set_xticklabels([str(nu) for nu in nus])
            top_ax.set_xlabel("Frequency [MHz]")
        ax.tick_params(length=2)
    ax.set_xlabel("Redshift")
    # scale bar: the box size
    out = Path(args.out) if args.out else REPO / "plots" / f"bands_{args.run}"
    for ext in ("png", "pdf"):
        fig.savefig(out.with_suffix(f".{ext}"), dpi=args.dpi)
    print(f"wrote {out}.png/.pdf: {n} bands of {args.band_width:g} cMpc")


# ====================================================================== global histories
# One colour per release (EOS26 black, EOS21 blue, EOS16 purple; as proposed for plot_xHI_history.ipynb, round 2,
# item C2); within a release the fiducial run is solid and the variant dashed; EOS26 lines thicker.
EOS_STYLE = {"EOS26 fiducial": dict(color="k", lw=1.8, ls="-", zorder=6),
             "EOS26 early EoR": dict(color="k", lw=1.8, ls="--", zorder=5),
             "EOS21": dict(color="#2C7BB6", lw=1.2, ls="-", zorder=4),
             "EOS16 faint galaxies": dict(color="#7B3294", lw=1.2, ls="-", zorder=4),
             "EOS16 bright galaxies": dict(color="#7B3294", lw=1.2, ls="--", zorder=4)}
EOS16_RUNS = {"EOS16 faint galaxies": "SmallHII_1024", "EOS16 bright galaxies": "LargeHII_1024"}
K_PS = 0.1  # 1/cMpc, the scale of the power-spectrum panel
LOG_FIELDS = ("neutral_fraction", "kinetic_temp_neutral", "spin_temperature")
GFS = {"label": 10, "tick": 9, "legend": 8}  # font sizes of the global figure [pt]


def delta2_at(k, d2, k0=K_PS):
    """Delta^2 at k0 by log-log interpolation over the finite bins (rows of d2: redshifts)."""
    out = []
    for row in np.atleast_2d(d2):
        ok = np.isfinite(row) & (row > 0) & (k > 0)
        out.append(10 ** np.interp(np.log10(k0), np.log10(k[ok]), np.log10(row[ok])) if ok.sum() > 1 else np.nan)
    return np.array(out)


def run_lc_dir(cache_name):
    """Lightcone directory of a cache, as postprocess/lightcone makes it (laptop: <repo>/<cache>/lightcones)."""
    sys.path.insert(1, str(REPO / "run_scripts"))
    sys.path.insert(1, str(REPO / "postprocess" / "lightcone"))
    import eos_lightcones as el
    import settings

    return el.default_out_dir(settings.DATA_ROOT / cache_name)


def store_means(lc, qs):
    """{q: (z, box mean)} at the node redshifts from the complete angular-plane stores in lc."""
    out = {}
    for q in qs:
        p = lc / "angular_plane" / f"{q}.h5"
        if p.exists():
            with h5py.File(p, "r") as h:
                if h.attrs.get("complete", False):
                    out[q] = (h["node_redshifts"][:], h["global_mean"][:])
    return out


def log_means(pattern):
    """{q: (z, box mean)} of LOG_FIELDS from the argument summaries of coeval logs (ComputeBrightnessTemp blocks)."""
    import glob
    import re

    res = {q: {} for q in LOG_FIELDS}
    for fn in sorted(glob.glob(str(pattern))):
        lines = open(fn, errors="replace").read().splitlines()
        for i, line in enumerate(lines):
            if "Calling ComputeBrightnessTemp with following args" not in line:
                continue
            z = round(float(lines[i + 1].split()[-1]), 4)
            for row in lines[i + 2:i + 200]:
                for q in LOG_FIELDS:
                    if f" {q}:" in row:
                        v = re.findall(r"[-+]?\d\.\d+e[-+]\d+", row)
                        if len(v) == 5:  # 1st, End, Min, Max, Mean
                            res[q][z] = float(v[4])
    return {q: (np.array(sorted(d)), np.array([d[k] for k in sorted(d)])) for q, d in res.items() if d}


def ps_curve(lc):
    """(z, Delta^2 at K_PS) from <lc>/power_spectra, T_b with RSDs if there, else without; None if neither."""
    for name in (RSD, "brightness_temp"):
        p = lc / "power_spectra" / f"{name}.npz"
        if p.exists():
            d = np.load(p)
            return d["z"], delta2_at(d["k"], d["delta2"])
    return None


def eos26_runs():
    """{label: {quantity: (z, mean)}} of the two EOS26 runs, and notes on where the fiducial run's curves come from.

    Early EoR: its production lightcones. Fiducial: its production lightcones once they exist; until then the
    coeval logs of the production run (x_HI, T_K, T_S, down to its lowest node so far), and below that, and for
    T_b and the power spectrum, the 300 cMpc test with the same parameters (its lightcones and coeval logs)."""
    qs = ["brightness_temp", *LOG_FIELDS]
    early_lc = run_lc_dir("EOS26_earlyEoR_cache")
    runs = {"EOS26 early EoR": store_means(early_lc, qs)}
    ps = ps_curve(early_lc)
    if ps:
        runs["EOS26 early EoR"]["delta2"] = ps
    fid_lc, test_lc = run_lc_dir("EOS26_cache"), run_lc_dir("EOS26_test_HIIDIM200")
    fid = store_means(fid_lc, qs)
    notes = []
    if len(fid) < len(qs):
        prod = log_means(REPO / "logs" / "EOS26_coeval_*.log")
        test = {**log_means(REPO / "logs" / "HII_DIM200_reference" / "full_test_*_coevals.log"),
                **store_means(test_lc, ["brightness_temp"])}
        zcut = min((z.min() for z, _ in prod.values()), default=np.inf)
        for q in qs:
            if q in fid:
                continue
            if q in prod:  # production above zcut, the test below
                zt, vt = test.get(q, (np.zeros(0), np.zeros(0)))
                below = zt < zcut - 1e-3
                fid[q] = (np.r_[zt[below], prod[q][0]], np.r_[vt[below], prod[q][1]])
            elif q in test:
                fid[q] = test[q]
        if np.isfinite(zcut):
            notes.append(f"fiducial x_HI, T_K, T_S: production coeval logs down to z = {zcut:.2f}, the 300 cMpc test below")
        notes.append("fiducial T_b: the 300 cMpc test")
    ps = ps_curve(fid_lc) or ps_curve(test_lc)
    if ps:
        fid["delta2"] = ps
        if not ps_curve(fid_lc):
            notes.append("fiducial Delta^2: the 300 cMpc test")
    runs = {"EOS26 fiducial": fid, **runs}
    return runs, notes, early_lc


def other_releases():
    """{release: {quantity: (z, values)}} of EOS21 (plots/EOS21) and EOS16 (plots/EOS16, 1024^3 runs)."""
    import re

    rel = {}
    d21 = REPO / "plots" / "EOS21"
    if d21.exists():
        z = np.fromfile(d21 / "Global" / "node_redshifts.bin")
        g = lambda n: np.fromfile(d21 / "Global" / f"global_{n}.bin")  # noqa: E731
        k = np.fromfile(d21 / "Power" / "1pt5Gpc_power_kbins_LC.bin")
        zc = np.fromfile(d21 / "Power" / "1pt5Gpc_power_zcentral_LC.bin")
        p = np.fromfile(d21 / "Power" / "1pt5Gpc_power_P21bins_LC.bin").reshape(zc.size, k.size)
        rel["EOS21"] = {"brightness_temp": (z, g("brightness_temp")), "neutral_fraction": (z, g("xH")),
                        "kinetic_temp_neutral": (z, g("Tk")), "spin_temperature": (z, g("Ts")),
                        "delta2": (zc, delta2_at(k, p))}
    for name, run in EOS16_RUNS.items():
        d = REPO / "plots" / "EOS16" / run / "Output_files"
        if not d.exists():
            continue
        rows = []  # power-spectrum files: z, neutral fraction and mean T_b in the name, (k, Delta^2, error) inside
        for f in (d / "Deldel_T_power_spec").glob("ps_no_halos_z*_1024_1600Mpc_v3"):
            m = re.search(r"_z([\d.]+)_nf([\d.]+)_.*_aveTb(-?[\d.]+)_", f.name)
            kk, d2 = np.loadtxt(f, usecols=(0, 1), unpack=True)
            rows.append((float(m[1]), float(m[2]), float(m[3]), delta2_at(kk, d2)[0]))
        z, nf, tb, d2 = np.array(sorted(rows)).T
        ge = np.loadtxt(next((d / "Ts_outs").glob("global_evolution_*_1024_1600Mpc")))  # z, ., T_K, x_e, T_S, T_CMB, ...
        rel[name] = {"brightness_temp": (z, tb), "neutral_fraction": (z, nf), "delta2": (z, d2),
                     "kinetic_temp_neutral": (ge[:, 0], ge[:, 2]), "spin_temperature": (ge[:, 0], ge[:, 4])}
    return rel


def global_histories(args):
    """Delta^2_21 at k = 0.1/cMpc, the mean T_b, the neutral fraction and the temperatures vs z, in one column."""
    plt = style()
    runs, notes, early_lc = eos26_runs()
    models = {**runs, **other_releases()}
    fig, axes = plt.subplots(4, 1, figsize=(args.col_width, 6.8), sharex=True)
    ax_ps, ax_tb, ax_x, ax_t = axes

    # the spread of the cells: the 16-84 and 2.5-97.5 percentiles of the angular plane of the run whose
    # production lightcones exist (the fiducial run's once they do)
    band_lc = run_lc_dir("EOS26_cache") if (run_lc_dir("EOS26_cache") / "angular_plane").exists() else early_lc

    def bands(ax, q, alpha=1.0):
        p = band_lc / "angular_plane" / f"{q}.h5"
        if not p.exists():
            return
        with h5py.File(p, "r") as h:
            zl = h["lightcone_redshifts"][::args.every]
            cells = h["lightcone"][:, ::args.every].astype(np.float64)
        lo2, lo1, hi1, hi2 = np.nanpercentile(cells, [2.5, 16, 84, 97.5], axis=0)
        ax.fill_between(zl, lo2, hi2, color="k", alpha=0.08 * alpha, lw=0, zorder=1)
        ax.fill_between(zl, lo1, hi1, color="k", alpha=0.16 * alpha, lw=0, zorder=1)

    def lines(ax, key, **kw):
        for name, d in models.items():
            if key in d:
                ax.plot(*d[key], **{**EOS_STYLE[name], **kw})

    lines(ax_ps, "delta2")
    ax_ps.set_yscale("log")
    ax_ps.set_ylim(top=ax_ps.get_ylim()[1] * 10)  # room for the k label
    ax_ps.set_ylabel(r"$\Delta^2_{21}$ [mK$^2$]")
    ax_ps.text(0.03, 0.94, rf"$k = {K_PS:g}$ cMpc$^{{-1}}$", transform=ax_ps.transAxes, ha="left", va="top",
               fontsize=GFS["legend"] + 1)
    missing = [n for n in runs if "delta2" not in runs[n]]
    if missing:
        ax_ps.text(0.97, 0.06, f"to come: {', '.join(missing)}", transform=ax_ps.transAxes, ha="right", va="bottom",
                   fontsize=GFS["legend"] - 1, color="#c62828")
    bands(ax_tb, "brightness_temp")
    lines(ax_tb, "brightness_temp")
    ax_tb.axhline(0, color="0.6", lw=0.5, zorder=0)
    ax_tb.set_ylabel(r"$\delta T_{\rm b}$ [mK]")
    bands(ax_x, "neutral_fraction")
    lines(ax_x, "neutral_fraction")
    ax_x.set_ylabel(r"$x_{\rm HI}$")
    ax_x.set_ylim(-0.02, 1.02)
    ax_x.legend([plt.Line2D([], [], **{k: v for k, v in EOS_STYLE[n].items() if k != "zorder"}) for n in models],
                list(models), fontsize=GFS["legend"], frameon=False, loc="lower right", handlelength=2.2)
    bands(ax_t, "kinetic_temp_neutral")
    lines(ax_t, "kinetic_temp_neutral")
    lines(ax_t, "spin_temperature", alpha=0.45)  # T_S: the same line, lighter
    zz = np.linspace(args.zmin, args.zmax, 100)
    ax_t.plot(zz, 2.7255 * (1 + zz), color="0.35", lw=0.9, ls=":")
    ax_t.set_yscale("log")
    ax_t.set_ylabel(r"$T$ [K]")
    ax_t.legend([plt.Line2D([], [], color="k", lw=1.6), plt.Line2D([], [], color="k", lw=1.6, alpha=0.45),
                 plt.Line2D([], [], color="0.35", lw=0.9, ls=":")],
                [r"$T_{\rm K}$", r"$T_{\rm S}$", r"$T_{\rm CMB}$"], fontsize=GFS["legend"], frameon=False,
                loc="upper right")
    for ax in axes:
        ax.tick_params(labelsize=GFS["tick"], length=2.5)
        ax.yaxis.label.set_size(GFS["label"])
    ax_t.set_xlabel("Redshift", fontsize=GFS["label"])
    ax_t.set_xlim(args.zmin, args.zmax)
    fig.tight_layout(pad=0.3, h_pad=0.25)
    out = Path(args.out) if args.out else REPO / "plots" / f"global_{args.run}"
    for ext in ("png", "pdf"):
        fig.savefig(out.with_suffix(f".{ext}"), dpi=args.dpi)
    print(f"wrote {out}.png/.pdf; bands from {band_lc}")
    for n in notes:
        print("For the caption:", n)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("what", choices=("arc", "bands", "global"))
    p.add_argument("--dir", default=None, help="lightcone directory (default: that of the run)")
    p.add_argument("--quantities", nargs="+", default=None)
    p.add_argument("--width", type=float, default=133, help="arc: longitudes shown, deg (default 133: 19 deg per sector)")
    p.add_argument("--zmin", type=float, default=5.0)
    p.add_argument("--zmax", type=float, default=35.0)
    p.add_argument("--pixels", type=int, default=5000, help="arc: image width in pixels (default 5000)")
    p.add_argument("--fig-width", type=float, default=7.0, help="figure width, inches (default 7)")
    p.add_argument("--col-width", type=float, default=3.46, help="global: figure width, inches (one A&A column)")
    p.add_argument("--dpi", type=int, default=600)
    p.add_argument("--box", type=float, default=2250, help="box size, cMpc")
    p.add_argument("--z-arcs", nargs="*", type=float, default=[6, 8, 10, 15, 20],
                   help="arc: redshifts of the faint arcs (default 6 8 10 15 20)")
    p.add_argument("--no-sky", dest="sky", action="store_false",
                   help="arc: without the full-sky map and the patch below it")
    p.add_argument("--sky-quantity", default="neutral_fraction", help="arc: quantity of the sky maps")
    p.add_argument("--sky-z", type=float, default=8.9, help="arc: redshift of the sky maps (nearest exported)")
    p.add_argument("--sky-zoom", type=float, default=8, help="arc: side of the patch zoom, deg (default 8)")
    p.add_argument("--band-width", type=float, default=300, help="bands: transverse width, cMpc (default 300)")
    p.add_argument("--cell", type=float, default=1.5, help="cell size, cMpc")
    p.add_argument("--every", type=int, default=4, help="global: every n-th slice for the spread (default 4)")
    p.add_argument("--run", default=None, help="name in the output file (default $EOS26_TEMPLATE or EOS26)")
    p.add_argument("--out", default=None, help="output file without suffix")
    args = p.parse_args(argv)
    import os

    args.run = args.run or os.environ.get("EOS26_TEMPLATE", "EOS26")
    {"arc": arc, "bands": bands, "global": global_histories}[args.what](args)


if __name__ == "__main__":
    main()
