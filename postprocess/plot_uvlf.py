"""UV luminosity functions of EOS26 at z = 6, 8, 10, 11, 12 and 14, as in Fig. 5 of Nikolic et al. (2026).

    python postprocess/plot_uvlf.py                 # plots/uvlf_EOS26.png/.pdf
    python postprocess/plot_uvlf.py --counts EOS26_earlyEoR_cache/uv_luminosity_functions.npz --label "EOS26 early EoR"

EOS26: the intrinsic M_UV histograms of the whole box (postprocess/galaxies/uv_luminosity_functions.py), with
the dust attenuation of Nikolic et al. (2026, Sect. 4.1): A_UV = 4.43 + 1.99 beta (Meurer et al. 1999), at
least 0, with beta(M_UV) from Bouwens et al. (2014, Table 3) below z = 8, Cullen et al. (2024, Eq. 4) at
8 <= z <= 10 and beta = -2.5 (no attenuation) above, evaluated at the observed M_UV. The catalogue holds only
galaxies in haloes above M_min, so the faint end is incomplete: the curve is dashed (and the panel shaded)
fainter than the magnitude at which galaxies in haloes within 0.05 dex of M_min make up --near-min of a bin.
Brighter than --bright (-20), where 21cmFAST's galaxy model is less reliable, the curve is also dashed and the
panel hatched.
Comparison: Nikolic et al.'s median UV LFs (postprocess/Ivan_UVLFs.txt), the CANUCS UV LFs they fitted
(Willott et al. 2024, Table 3, in the same colour) and the data in postprocess/UVLF_data (21CMMC files).
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# STIX: the Times-like font of A&A's text (as the other paper figures)
plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 9,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6})

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PANELS = [6, 8, 10, 11, 12, 14]
FS = {"label": 12, "tick": 10.5, "legend": 9.5, "panel": 11}
EOS_COLOUR, IVAN_COLOUR, DATA_COLOUR = "k", "#b5543c", "0.45"
DATA = [  # (file prefix in UVLF_data, label, marker, {panel z: file z}); the 21CMMC files
    ("LF", "Bouwens+15, +17; Oesch+18", "s", {6: "6", 8: "8", 10: "10"}),  # z6: B17 (HFF), z8: B15, z10: O18
    ("Donnan24_LF", "Donnan+24", "o", {10: "10", 11: "11", 12: "12", 14: "14"}),
    ("Chemerynska26_LF", "Chemerynska+26", "^", {10: "10", 11: "11"}),
]
# Willott et al. (2024), Table 3: (M_UV bin centre, phi, +err, -err) in 1e-5 Mpc^-3 mag^-1; err None = 1-sigma upper limit
WILLOTT24 = {
    8: [(-20.75, 8.8, 7.1, 4.4), (-20.25, 13, 6, 6), (-19.75, 42, 11, 11), (-19.25, 80, 18, 18),
        (-18.75, 116, 28, 28), (-18.25, 253, 79, 79)],  # 7.5 < z < 8.5
    10: [(-20.5, 1.7, None, None), (-19.5, 12.4, 4.9, 4.9), (-18.5, 10.0, 9.9, 5.7)],  # 9.5 < z < 11
    12: [(-20.5, 2.0, None, None), (-19.5, 2.6, 3.4, 1.7), (-18.5, 4.8, 11.1, 4.1)],  # 11 < z < 12.5
}
IVAN_Z = [6, 7, 8, 9, 10, 11, 12.5, 14.5]  # rows of Ivan_UVLFs.txt, at M_UV = -23 to -17
# beta at M_UV = -19.5 and d beta / d M_UV (Bouwens et al. 2014, Table 3), by mean redshift
BOUWENS14 = {3.8: (-1.85, -0.11), 5.0: (-1.91, -0.14), 5.9: (-2.00, -0.20), 7.0: (-2.05, -0.20)}


def beta(muv, z):
    """UV slope at observed M_UV: Bouwens+14 below z = 8, Cullen+24 Eq. 4 at 8-10, -2.5 above."""
    if z < 8:
        b0, slope = BOUWENS14[min(BOUWENS14, key=lambda zz: abs(zz - z))]
        return b0 + slope * (muv + 19.5)
    if z <= 10:
        return -2.19 - 0.15 * (muv + 19.0)
    return np.full_like(muv, -2.5)


def observed(muv, z):
    """Observed M_UV for intrinsic muv: M_obs = M_int + A_UV(beta(M_obs)), A_UV = max(0, 4.43 + 1.99 beta)."""
    m = np.array(muv, float)
    for _ in range(50):
        m = muv + np.maximum(0.0, 4.43 + 1.99 * beta(m, z))
    return m


def eos26_lfs(path, width, near_min):
    """{panel z: (bin centres, phi, Poisson sigma, n, completeness limit)} from uv_luminosity_functions.py."""
    d = np.load(path)
    fine = d["muv_edges"]
    centres = 0.5 * (fine[1:] + fine[:-1])
    edges = np.arange(-26.0, -9.999, width)
    out = {}
    for zr, n_fine, near in zip(d["z_request"], d["counts"], d["counts_near_min"]):
        m_obs = observed(centres, zr)
        n = np.histogram(m_obs, edges, weights=n_fine)[0]
        n_near = np.histogram(m_obs, edges, weights=near)[0]
        mids = 0.5 * (edges[1:] + edges[:-1])
        frac = np.where(n > 0, n_near / np.maximum(n, 1), 0.0)
        lim = mids[np.argmax(frac >= near_min)] if (frac >= near_min).any() else np.inf
        out[int(round(zr))] = (mids, n / (width * d["volume"]), np.sqrt(n) / (width * d["volume"]), n, lim)
    return out


def load_data(prefix, zstr):
    f = HERE / "UVLF_data" / f"{prefix}_lfuncs_z{zstr}.npz"
    if not f.exists():
        return None
    d = np.load(f)
    return d["Muv"], d["lfunc"], np.load(HERE / "UVLF_data" / f"{prefix}_sigmas_z{zstr}.npz")["sigma"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--counts", default=REPO / "EOS26_earlyEoR_cache" / "uv_luminosity_functions.npz")
    p.add_argument("--label", default="EOS26 early EoR", help="legend label of the EOS26 curves")
    p.add_argument("--width", type=float, default=0.25, help="M_UV bin width of the EOS26 curves [mag]")
    p.add_argument("--min-count", type=int, default=10, help="galaxies per bin below which the curve stops")
    p.add_argument("--near-min", type=float, default=0.05,
                   help="fraction of a bin in haloes within 0.05 dex of M_min beyond which the curve is dashed")
    p.add_argument("--bright", type=float, default=-20.0,
                   help="M_UV brighter than which 21cmFAST is less reliable: dashed curve, hatched panel")
    p.add_argument("--xlim", type=float, nargs=2, default=[-24.5, -13.5])
    p.add_argument("--ylim", type=float, nargs=2, default=[1e-9, 1e0])
    p.add_argument("--fig-width", type=float, default=7.0)
    p.add_argument("--fig-height", type=float, default=5.0)
    p.add_argument("--dpi", type=int, default=600)
    p.add_argument("--out", default=REPO / "plots" / "uvlf_EOS26")
    args = p.parse_args(argv)

    eos = eos26_lfs(args.counts, args.width, args.near_min) if Path(args.counts).exists() else {}
    if not eos:
        print(f"no {args.counts}: data only")
    ivan = np.loadtxt(HERE / "Ivan_UVLFs.txt")
    ivan_muv = np.linspace(-23, -17, ivan.shape[1])

    fig, axs = plt.subplots(2, 3, sharex=True, sharey=True, figsize=(args.fig_width, args.fig_height))
    for ax, z in zip(axs.flat, PANELS):
        if z in eos:
            m, phi, sig, n, lim = eos[z]
            ok = n >= args.min_count
            ax.fill_between(m[ok], (phi - sig)[ok], (phi + sig)[ok], color=EOS_COLOUR, alpha=0.2, lw=0)
            for part, ls in ((m <= args.bright, "--"), ((m >= args.bright) & (m <= lim), "-"), (m >= lim, "--")):
                ax.plot(m[ok & part], phi[ok & part], color=EOS_COLOUR, lw=1.6, ls=ls)
            ax.axvspan(lim, args.xlim[1], color="0.9", lw=0, zorder=0)
            ax.axvspan(args.xlim[0], args.bright, facecolor="none", edgecolor="0.8", hatch="////", lw=0, zorder=0)
        k = int(np.argmin(np.abs(np.array(IVAN_Z) - z)))
        ax.plot(ivan_muv, ivan[k], color=IVAN_COLOUR, lw=1.4)
        for prefix, _, marker, files in DATA:
            if z in files and (d := load_data(prefix, files[z])) is not None:
                ax.errorbar(d[0], d[1], yerr=d[2], color=DATA_COLOUR, ls="none", marker=marker, ms=3.5, lw=0.8,
                            mfc="white", mew=0.8)
        for mw, ph, up, lo in WILLOTT24.get(z, []):
            if up is None:  # 1-sigma upper limit
                ax.errorbar(mw, ph * 1e-5, yerr=0.5 * ph * 1e-5, uplims=True, color=IVAN_COLOUR, marker="_", ms=6, lw=0.9)
            else:
                ax.errorbar(mw, ph * 1e-5, yerr=[[lo * 1e-5], [up * 1e-5]], color=IVAN_COLOUR, marker="o", ms=3.5,
                            lw=0.9, ls="none")
        ax.text(0.05, 0.93, f"$z = {z}$", transform=ax.transAxes, fontsize=FS["panel"], va="top")
        ax.set_yscale("log")
        ax.set_xlim(*args.xlim)
        ax.set_ylim(*args.ylim)
        ax.tick_params(labelsize=FS["tick"], length=2.5, which="both")
        ax.yaxis.set_major_locator(plt.LogLocator(base=100.0, numticks=10))
        ax.yaxis.set_minor_locator(plt.LogLocator(base=10.0, subs=(1.0,), numticks=20))
        ax.yaxis.set_minor_formatter(plt.NullFormatter())
        ax.xaxis.set_major_locator(plt.MultipleLocator(2))
    for ax in axs[1]:
        ax.set_xlabel(r"$M_{\rm UV}$ [mag]", fontsize=FS["label"])
    for ax in axs[:, 0]:
        ax.set_ylabel(r"$\phi$ [cMpc$^{-3}$ mag$^{-1}$]", fontsize=FS["label"])

    handles = [Line2D([], [], color=EOS_COLOUR, lw=1.6, label=args.label),
               Line2D([], [], color=IVAN_COLOUR, lw=1.4, label="Nikolic+26 (median)"),
               Line2D([], [], color=IVAN_COLOUR, ls="none", marker="o", ms=4, label="Willott+24")]
    handles += [Line2D([], [], color=DATA_COLOUR, ls="none", marker=mk, ms=4, mfc="white", mew=0.8, label=lab)
                for _, lab, mk, _ in DATA]
    if eos:  # filled column by column: EOS26 and Nikolic+26, the grey data, the two shaded areas
        handles += [Patch(color="0.9", label="incomplete catalogue"),
                    Patch(facecolor="none", edgecolor="0.8", hatch="////", lw=0, label="bright end, less reliable")]
    fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=FS["legend"], frameon=False)
    fig.tight_layout(rect=(0, 0, 1, 0.855), h_pad=0.3, w_pad=0.3)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".png"), dpi=args.dpi)
    fig.savefig(out.with_suffix(".pdf"))
    print(f"wrote {out}.png/.pdf")
    for z in PANELS:
        if z in eos:
            print(f"z = {z}: complete (near-min fraction < {args.near_min}) brighter than M_UV = {eos[z][4]:.2f}")


if __name__ == "__main__":
    main()
