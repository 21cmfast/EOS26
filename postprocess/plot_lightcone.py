"""Lightcone plots of the EOS26 run, from whatever boxes are cached so far.

    python postprocess/plot_lightcone.py                                  # default quantities
    python postprocess/plot_lightcone.py --quantities density stellar_mass
    python postprocess/plot_lightcone.py --quantities all                 # everything cached
    python postprocess/plot_lightcone.py --list                           # what is there so far
    python postprocess/plot_lightcone.py --test                           # HII_DIM=200 reference

Each quantity comes from its own cached boxes (postprocess/eos_boxes.py):
  * density, velocity_z                    PerturbedField      every redshift
  * stellar_mass, sfr, halo_mass (and the  HaloCatalog         every redshift
    _acg/_mcg parts)
  * brightness_temp, spin_temperature,     coeval boxes        the redshifts the coeval
    neutral_fraction, ... (see --list)                         jobs have done so far
Redshifts without boxes yet are left grey, so rerunning this as the coeval jobs go on
extends the same lightcones. Only new or changed boxes are read again: the plane each
box contributes is kept in <cache>/lightcone_planes/.

Geometry: a rectilinear lightcone along the last axis of the boxes. The comoving
distance from the lowest to the highest node redshift is cut into cells; each takes
the plane at that distance (modulo the box length) of the two node-redshift boxes
around it, interpolated linearly in comoving distance. What is shown is the slab
x0 <= x < x0 + width (cells) of the boxes. Halo quantities are the halo properties
from 21cmFAST's own scaling relations (with the stored stochasticity) summed in each
cell of that slab, per Mpc^3; feedback (LW, photoheating) is included once the
coevals of the previous redshift exist. This is a picture of the run, not a substitute
for the lightcone of postprocess/make_lightcone.py.

Output: plots/lightcones_<run>_v<21cmFAST version>.png (or --out).
"""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
import settings  # noqa: E402

DEFAULT = ["density", "stellar_mass", "brightness_temp", "spin_temperature", "neutral_fraction"]

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--test", action="store_true", help=f"the HII_DIM={settings.TEST_HII_DIM} test reference")
parser.add_argument("--compare", action="store_true", help="the cache of a --compare test run (with --test)")
parser.add_argument("--quantities", nargs="+", default=DEFAULT,
                    help=f"'all' for every quantity with cached boxes; default: {' '.join(DEFAULT)}")
parser.add_argument("--x0", type=int, default=0, help="first cell of the slab shown (first box axis)")
parser.add_argument("--width", type=int, default=1, help="slab thickness in cells (default 1)")
parser.add_argument("--zmin", type=float, default=None, help="default: lowest node redshift")
parser.add_argument("--zmax", type=float, default=None, help="default: highest node redshift")
parser.add_argument("--list", action="store_true", help="list the quantities and the redshifts cached so far")
parser.add_argument("--out", default=None, help="output file (default plots/lightcones_<run>_v<version>.png)")
parser.add_argument("--log-file", default=None, help="log to this file (default: the terminal)")
args = parser.parse_args()

if args.log_file:
    settings.setup_logging(args.log_file)
else:
    settings.setup_logger()
log = logging.getLogger("21cmFAST")

import numpy as np  # noqa: E402
import eos_boxes as eb  # noqa: E402

run = eb.Run(test=args.test, compare=args.compare)


def available(q: str) -> list[float]:
    """Node redshifts with a cached box holding q ([] if the boxes don't store it)."""
    kind = eb.source_kind(q)
    have = [z for z in run.redshifts if run.path(kind, z) is not None]
    if have and kind != "HaloCatalog" and not eb.has_field(run.path(kind, have[0]), kind, q):
        return []
    return have


if args.list:
    for q in sorted(eb.FIELD_KIND) + sorted(eb.HALO_QUANTITIES):
        kind = eb.source_kind(q)
        have = available(q)
        rng = f"z = {min(have):.2f} - {max(have):.2f}" if have else "none (yet)"
        print(f"{q:28s} {kind:17s} {len(have):3d}/{len(run.redshifts)} redshifts  {rng}")
    sys.exit(0)

if args.quantities == ["all"]:
    args.quantities = [q for q in [*eb.FIELD_KIND, *eb.HALO_QUANTITIES] if available(q)]
for q in args.quantities:
    kind = eb.source_kind(q)  # unknown quantity -> KeyError with the list of known ones
    first = next((run.path(kind, z) for z in run.redshifts if run.path(kind, z) is not None), None)
    if first is not None and kind != "HaloCatalog" and not eb.has_field(first, kind, q):
        sys.exit(f"{q} is not stored in the {kind} boxes of this run (see --list)")

store = Path(run.cache_dir) / "lightcone_planes" / f"x{args.x0}_w{args.width}"


def planes_at(z: float, quantities: list[str]) -> dict:
    """{quantity: plane} for the quantities whose box at z exists (from the store if current)."""
    out, todo_fields, todo_halos = {}, [], []
    for q in quantities:
        kind = eb.source_kind(q)
        src = run.path(kind, z)
        if src is None:
            continue
        f = store / q / f"z{z:.4f}.npz"
        if f.exists():
            with np.load(f) as saved:
                fresh = float(saved["src_mtime"]) == src.stat().st_mtime
                if kind == "HaloCatalog" and fresh and not bool(saved["feedback"]):
                    # made before the feedback boxes (previous redshift's coevals) existed
                    higher = [zz for zz in run.redshifts if zz > z + 1e-6]
                    fresh = not (higher and run.path("TsBox", higher[0]) and run.path("IonizedBox", higher[0]))
                if fresh:
                    out[q] = saved["plane"]
                    continue
        (todo_halos if kind == "HaloCatalog" else todo_fields).append(q)
    # A box a running coeval job is still writing can't be read yet (or is locked):
    # it is skipped now and read on the next run.
    for q in todo_fields:
        kind = eb.FIELD_KIND[q]
        src = run.path(kind, z)
        try:
            out[q] = eb.read_plane(src, kind, q, x0=args.x0, width=args.width)
        except (OSError, KeyError) as e:
            log.warning(f"skipping {q} at z={z:.4f} for now: {type(e).__name__}: {e}")
            continue
        _save(q, z, out[q], src, feedback=True)
    if todo_halos:
        src = run.path("HaloCatalog", z)
        try:
            planes, feedback = eb.halo_planes(run, z, todo_halos, x0=args.x0, width=args.width)
        except (OSError, KeyError) as e:
            log.warning(f"skipping the halo quantities at z={z:.4f} for now: {type(e).__name__}: {e}")
            planes = {}
        for q, p in planes.items():
            out[q] = p
            _save(q, z, p, src, feedback)
    return out


def _save(q, z, plane, src, feedback):
    f = store / q / f"z{z:.4f}.npz"
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp.npz")
    np.savez(tmp, plane=plane, src_mtime=src.stat().st_mtime, feedback=feedback)
    tmp.replace(f)


# ---------------------------------------------------------------- lightcone geometry
zs = np.array(run.redshifts)
zmin = zs[0] if args.zmin is None else max(args.zmin, zs[0])
zmax = zs[-1] if args.zmax is None else min(args.zmax, zs[-1])
zs = zs[(zs >= zs[zs <= zmin].max()) & (zs <= zs[zs >= zmax].min())]
cosmo = run.inputs.cosmo_params.cosmo
D = cosmo.comoving_distance(zs).to_value("Mpc")
d = np.arange(cosmo.comoving_distance(zmin).to_value("Mpc"), cosmo.comoving_distance(zmax).to_value("Mpc"), run.cell)
k = np.round((d - D[0]) / run.cell).astype(int) % run.n_los      # plane of the box along the line of sight
i = np.clip(np.searchsorted(D, d, side="right") - 1, 0, len(zs) - 2)  # node redshifts zs[i], zs[i+1]
w = ((d - D[i]) / (D[i + 1] - D[i])).astype(np.float32)
z_of_d = np.interp(d, D, zs)

t0 = time.perf_counter()
lc = {q: np.full((run.n, d.size), np.nan, np.float32) for q in args.quantities}
prev = planes_at(zs[0], args.quantities)
for b in range(len(zs) - 1):
    nxt = planes_at(zs[b + 1], args.quantities)
    js = np.nonzero(i == b)[0]
    for q in args.quantities:
        if js.size and q in prev and q in nxt:
            lc[q][:, js] = (1 - w[js]) * prev[q][:, k[js]] + w[js] * nxt[q][:, k[js]]
    prev = nxt
log.info(f"lightcone planes for {len(zs)} redshifts in {time.perf_counter() - t0:.0f} s (store: {store})")

# ---------------------------------------------------------------- plot
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import colormaps, colors, ticker  # noqa: E402

plt.rcParams.update({"font.size": 14, "font.family": "serif"})
eor = colors.LinearSegmentedColormap.from_list(
    "EoR", [(0, "white"), (0.21, "yellow"), (0.42, "orange"), (0.63, "red"),
            (0.86, "black"), (0.9, "blue"), (1, "cyan")])
if "EoR" not in colormaps:
    colormaps.register(cmap=eor)

# label, colour map, scale. Scales: lin (5-95th percentile), log (positive values,
# 5-99.5th percentile; zeros in the darkest colour), sym (symmetric about 0), eor
# (fixed -150..30 mK), unit (0..1), zreion (only reionised cells).
SPEC = {
    "density": (r"$\delta$", "viridis", "lin"),
    "velocity_z": (r"$v_z$", "RdBu_r", "sym"),
    "stellar_mass": (r"$\rho_\star$ [M$_\odot$ Mpc$^{-3}$]", "magma", "log"),
    "stellar_mass_acg": (r"$\rho_\star$ (ACG) [M$_\odot$ Mpc$^{-3}$]", "magma", "log"),
    "stellar_mass_mcg": (r"$\rho_\star$ (MCG) [M$_\odot$ Mpc$^{-3}$]", "magma", "log"),
    "sfr": (r"SFRD [M$_\odot$ yr$^{-1}$ Mpc$^{-3}$]", "inferno", "log"),
    "sfr_acg": (r"SFRD (ACG) [M$_\odot$ yr$^{-1}$ Mpc$^{-3}$]", "inferno", "log"),
    "sfr_mcg": (r"SFRD (MCG) [M$_\odot$ yr$^{-1}$ Mpc$^{-3}$]", "inferno", "log"),
    "halo_mass": (r"$\rho_{\rm halo}$ [M$_\odot$ Mpc$^{-3}$]", "cividis", "log"),
    "brightness_temp": (r"$\delta T_{21}$ [mK]", "EoR", "eor"),
    "tau_21": (r"$\tau_{21}$", "YlGnBu", "log"),
    "spin_temperature": (r"$T_S$ [K]", "inferno", "log"),
    "kinetic_temp_neutral": (r"$T_K$ [K]", "magma", "log"),
    "kinetic_temperature": (r"$T_K$ (IonizedBox) [K]", "magma", "log"),
    "xray_ionised_fraction": (r"$x_e$", "cividis", "log"),
    "J_21_LW": (r"$J_{21,LW}$", "Blues", "log"),
    "neutral_fraction": (r"$x_{HI}$", "hot", "unit"),
    "cumulative_recombinations": ("cumul. recombs", "Reds", "lin"),
    "z_reion": (r"$z_{reion}$", "plasma", "zreion"),
    "ionisation_rate_G12": (r"$\Gamma_{12}$", "viridis", "log"),
    "mean_free_path": ("mean free path [Mpc]", "viridis", "log"),
    "sfrd_acg": (r"SFRD (ACG, grid)", "magma", "log"),
    "sfrd_mcg": (r"SFRD (MCG, grid)", "magma", "log"),
    "xray_emissivity": (r"X-ray emissivity", "inferno", "log"),
    "n_ion": (r"$n_{ion}$", "viridis", "log"),
    "fesc_weighted_sfrd": (r"$f_{esc}$-weighted SFRD", "magma", "log"),
}


def _norm(data, scale):
    """Colour normalisation and the data to draw (NaN = not computed yet)."""
    finite = data[np.isfinite(data)]
    if scale == "eor":
        return colors.Normalize(-150, 30), data
    if scale == "unit":
        return colors.Normalize(0, 1), data
    if scale == "sym":
        v = np.percentile(np.abs(finite), 99) if finite.size else 1
        return colors.Normalize(-v, v), data
    if scale in ("log", "zreion"):
        positive = finite[finite > 0]
        if positive.size == 0:
            return colors.Normalize(0, 1), data
        lo, hi = np.percentile(positive, [5, 99.5])
        hi = max(hi, lo * (1 + 1e-6))
        if scale == "zreion":
            return colors.Normalize(lo, hi), np.where(data > 0, data, np.nan)
        shown = np.where(np.isfinite(data) & (data <= lo), lo, data)  # zeros: darkest colour
        if hi < 30 * lo:  # less than ~1.5 decades: linear reads better
            return colors.Normalize(lo, hi), shown
        return colors.LogNorm(lo, hi), shown
    lo, hi = (np.percentile(finite, [5, 95]) if finite.size else (0, 1))
    return colors.Normalize(lo, hi if hi > lo else lo + 1), data


keys = args.quantities
ncols = min(len(keys), 6)
nrows = int(np.ceil(len(keys) / ncols))
fig, axs = plt.subplots(nrows=nrows, ncols=ncols, sharey=True, figsize=(3.6 * ncols, 13 * nrows), squeeze=False,
                        layout="constrained")
L = run.n * run.cell
tick_z = [z for z in (5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 23, 26, 30, 35) if zmin <= z <= zmax]
tick_d = cosmo.comoving_distance(tick_z).to_value("Mpc")
for ax, q in zip(axs.flat, keys):
    label, cmap_name, scale = SPEC.get(q, (q, "viridis", "lin"))
    cmap = colormaps[cmap_name].copy()
    cmap.set_bad("0.85")
    data = lc[q]
    norm, shown = _norm(data, scale)
    im = ax.imshow(shown.T, origin="lower", aspect="auto", extent=[0, L, d[0], d[-1] + run.cell],
                   norm=norm, cmap=cmap, interpolation="nearest")
    cb = fig.colorbar(im, orientation="horizontal", ax=ax, label=label, pad=0.04)
    if isinstance(norm, colors.LogNorm):
        cb.ax.xaxis.set_major_locator(ticker.LogLocator(numticks=4))
        cb.ax.xaxis.set_minor_formatter(ticker.NullFormatter())
    else:
        cb.ax.xaxis.set_major_locator(ticker.MaxNLocator(3))
    done = np.isfinite(data).any(axis=0)
    if done.any() and not done.all():
        ax.set_title(f"z = {z_of_d[done].min():.1f}–{z_of_d[done].max():.1f} so far", fontsize=11)
    elif not done.any():
        ax.set_title("no boxes yet", fontsize=11)
    ax.set_xlabel("Mpc", labelpad=1)
    ax.set_yticks(tick_d, [f"{z:g}" for z in tick_z])
for ax in axs.flat[len(keys):]:
    ax.set_visible(False)
for row in axs:
    row[0].set_ylabel("Redshift")
fig.suptitle(f"{run.tag}, slab x = {args.x0 * run.cell:g}–{(args.x0 + args.width) * run.cell:g} Mpc "
             f"(21cmFAST {run.version})")
out = Path(args.out or eb.PLOTS / f"lightcones_{run.tag}_v{run.version}.png")
out.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out, bbox_inches="tight", dpi=100)
log.info(f"Saved {len(keys)} lightcones to {out}")
