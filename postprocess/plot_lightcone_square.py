"""Page-sized square picture of an EOS26 angular lightcone: the circle stretched onto a square.

    python postprocess/plot_lightcone_square.py                  # the test simulation (default)
    python postprocess/plot_lightcone_square.py --production     # EOS26
    python postprocess/plot_lightcone_square.py --no-text        # without any text (slides)
    python postprocess/plot_lightcone_square.py --circle         # the unstretched disc (logo)
    python postprocess/plot_lightcone_square.py --size 2000      # quick preview

Input: the ring lightcone of postprocess/make_angular_lightcone.py,
<cache>/lightcone_ring_v<21cmFAST version>.h5 (or --lightcone FILE). It is an angular lightcone
whose pixels all lie on one great circle around an observer at the centre of the box, so each
quantity is a (longitude, distance) array.

Picture: the angle on the page is the longitude on that circle, and the distance from the centre
is cosmic time, from z = 5 next to the observer to z = 35 at the rim (--order hiz_in turns it
inside out; --radius distance makes it linear in comoving distance). The quantities share the
circle in equal sectors, listed clockwise starting just left of straight down, and blend into
each other at the seams. The disc is then stretched onto the square with the elliptical-grid map
(Fong 2015), which keeps the axes and diagonals straight, so with 8 quantities the seams stay
straight; the picture is not to scale. Each page pixel is the mean of the lightcone samples that
land in it, or a bilinear sample where the lightcone is coarser than the pixels, so the inner
rings do not alias.

Output: plots/lightcone_square_<run>_v<version>[_circle][_hiz_in][_distance][_notext].png
(or --out).
"""
import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
import settings  # noqa: E402

# clockwise, starting just left of straight down (as in the mock-up the figure is based on)
DEFAULT = ["density", "sfrd_acg", "kinetic_temp_neutral", "J_21_LW",
           "neutral_fraction", "brightness_temp", "spin_temperature", "cumulative_recombinations"]

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
which = parser.add_mutually_exclusive_group()
which.add_argument("--test", dest="production", action="store_false",
                   help=f"the HII_DIM={settings.TEST_HII_DIM} test simulation (default)")
which.add_argument("--production", dest="production", action="store_true", help="the EOS26 production run")
parser.set_defaults(production=False)
parser.add_argument("--lightcone", default=None, help="ring lightcone file (default: the run's, see above)")
parser.add_argument("--quantities", nargs="+", default=DEFAULT,
                    help="lightcone quantities, clockwise from just left of straight down; 8 keeps the "
                         f"seams on the axes and diagonals (default: {' '.join(DEFAULT)})")
parser.add_argument("--order", choices=("lowz_in", "hiz_in"), default="lowz_in",
                    help="lowz_in: z = 5 at the centre, 35 at the rim (default); hiz_in: the reverse")
parser.add_argument("--radius", choices=("time", "distance"), default="time",
                    help="radius linear in cosmic time (default) or in comoving distance")
parser.add_argument("--circle", action="store_true", help="keep the disc round (black corners) instead of stretching it")
parser.add_argument("--no-text", action="store_true", help="no title, labels or redshift rings")
parser.add_argument("--zmin", type=float, default=5.0, help="lowest redshift shown (default 5)")
parser.add_argument("--zmax", type=float, default=35.0, help="highest redshift shown (default 35)")
parser.add_argument("--size", type=int, default=6000, help="width = height in pixels (default 6000: 20 in at 300 dpi)")
parser.add_argument("--dpi", type=int, default=300, help="dots per inch written to the PNG (default 300)")
parser.add_argument("--out", default=None, help="output file (default: see above)")
parser.add_argument("--log-file", default=None, help="log to this file (default: the terminal)")
args = parser.parse_args()

if args.log_file:
    settings.setup_logging(args.log_file)
else:
    settings.setup_logger()
log = logging.getLogger("21cmFAST")

import h5py  # noqa: E402
import numpy as np  # noqa: E402
from scipy.ndimage import map_coordinates  # noqa: E402

import eos_boxes as eb  # noqa: E402

run = eb.Run(test=not args.production)
cosmo = run.inputs.cosmo_params.cosmo


def ring_lightcone_path(cache_dir) -> Path:
    """<cache>/lightcone_ring_v<version>.h5 -- the same name as in make_angular_lightcone.py."""
    p = Path(settings.lightcone_path(cache_dir))
    return p.with_name(p.name.replace("lightcone_", "lightcone_ring_", 1))


lc_path = Path(args.lightcone) if args.lightcone else ring_lightcone_path(run.cache_dir)
if not lc_path.exists():
    sys.exit(f"No ring lightcone at {lc_path} yet. Make it with "
             f"postprocess/make_angular_lightcone.py{'' if args.production else ' --test'} "
             "once the coevals are done, or pass --lightcone.")

# ---------------------------------------------------------------- the lightcone file
f = h5py.File(lc_path, "r")
if "lightcones" not in f:
    sys.exit(f"{lc_path} is not a 21cmFAST lightcone file")
missing = [q for q in args.quantities if q not in f["lightcones"]]
if missing:
    sys.exit(f"{missing} are not in {lc_path}; it has {sorted(f['lightcones'])}")
first = f["lightcones"][args.quantities[0]]
if first.ndim != 2:
    sys.exit(f"{lc_path} holds {first.ndim}D lightcones; this needs the 2D ring lightcone of "
             "make_angular_lightcone.py (a rectilinear lightcone has no ring)")
n_lon = first.shape[0]
k_lo = int(f.attrs.get("lowz_buffer_pixels", 0))
k_hi = first.shape[1] - int(f.attrs.get("highz_buffer_pixels", 0))
dist = np.asarray(f["lightcone_distances"][k_lo:k_hi], dtype=np.float64)  # cMpc
lon = (np.asarray(f["ring/longitude"][:], dtype=np.float64) if "ring/longitude" in f
       else np.arange(n_lon) * (2 * np.pi / n_lon))
version = f.attrs.get("__version__", run.version)
version = version.decode() if isinstance(version, bytes) else str(version)

# ---------------------------------------------------------------- radius <-> redshift
zg = np.linspace(4.0, 40.0, 4000)
dg = cosmo.comoving_distance(zg).to_value("Mpc")
z_of_d = lambda d: np.interp(d, dg, zg)  # noqa: E731
d_of_z = lambda z: np.interp(z, zg, dg)  # noqa: E731
zmin = max(args.zmin, float(z_of_d(dist.min())))
zmax = min(args.zmax, float(z_of_d(dist.max())))
zr = np.linspace(zmin, zmax, 4000)
key = -cosmo.age(zr).to_value("Gyr") if args.radius == "time" else d_of_z(zr)
frac_z = (key - key[0]) / (key[-1] - key[0])           # 0 at zmin, 1 at zmax
if args.order == "hiz_in":
    frac_z = 1 - frac_z
R_IN = 0.11                                            # observer disc (z < zmin, or z > zmax)
R_OUT = 0.95 if (args.circle and not args.no_text) else 1.0
r_of_z = lambda z: R_IN + np.interp(z, zr, frac_z) * (R_OUT - R_IN)  # noqa: E731
_o = np.argsort(frac_z)
z_of_r = lambda r: np.interp((r - R_IN) / (R_OUT - R_IN), frac_z[_o], zr[_o])  # noqa: E731
stretch = not args.circle


def square_to_disc(u, v):
    """Elliptical-grid map (Fong 2015): the square [-1, 1]^2 onto the unit disc."""
    return u * np.sqrt(1 - v * v / 2), v * np.sqrt(1 - u * u / 2)


def disc_to_square(x, y):
    """Inverse of square_to_disc."""
    a, b, s = 2 + x * x - y * y, 2 - x * x + y * y, 2 * np.sqrt(2)
    u = 0.5 * np.sqrt(np.clip(a + s * x, 0, None)) - 0.5 * np.sqrt(np.clip(a - s * x, 0, None))
    v = 0.5 * np.sqrt(np.clip(b + s * y, 0, None)) - 0.5 * np.sqrt(np.clip(b - s * y, 0, None))
    return u, v


# ---------------------------------------------------------------- page geometry
N = args.size
c = ((np.arange(N, dtype=np.float32) + 0.5) / N * 2 - 1)
U, V = np.broadcast_to(c[None, :], (N, N)), np.broadcast_to(-c[:, None], (N, N))  # row 0 at the top
X, Y = square_to_disc(U, V) if stretch else (U, V)
R = np.hypot(X, Y)
TH = np.degrees(np.arctan2(X, Y))                      # page angle: 0 up, clockwise
del X, Y
ring = (R >= R_IN) & (R <= R_OUT)
D_pix = np.full((N, N), np.nan, np.float32)
D_pix[ring] = d_of_z(z_of_r(R[ring]))

# ---------------------------------------------------------------- colours
from matplotlib import colormaps, colors  # noqa: E402

eor = colors.LinearSegmentedColormap.from_list(
    "EoR", [(0, "white"), (0.21, "yellow"), (0.42, "orange"), (0.63, "red"),
            (0.86, "black"), (0.9, "blue"), (1, "cyan")])
# label, colour map, scale: lin (percentiles), log (positive values; zeros darkest),
# log1p (log10(1 + x)), unit (0..1), eor (fixed -150..30 mK), zreion (only reionised cells)
SPEC = {
    "density": ("Density", "magma", "log1p"),
    "velocity_z": ("Velocity", "RdBu_r", "lin"),
    "sfrd_acg": ("Star formation", "afmhot", "log"),
    "sfrd_mcg": ("Star formation (MCGs)", "afmhot", "log"),
    "xray_emissivity": ("X-ray emissivity", "inferno", "log"),
    "n_ion": ("Ionising emissivity", "viridis", "log"),
    "fesc_weighted_sfrd": ("Escaping star formation", "magma", "log"),
    "kinetic_temp_neutral": ("Gas temperature", "inferno", "log"),
    "kinetic_temperature": ("Gas temperature", "inferno", "log"),
    "spin_temperature": ("Spin temperature", "plasma", "log"),
    "xray_ionised_fraction": ("X-ray ionisation", "cividis", "log"),
    "J_21_LW": ("Lyman–Werner", "Blues_r", "log"),
    "neutral_fraction": ("Neutral fraction", "bone", "unit"),
    "brightness_temp": ("21-cm signal", eor, "eor"),
    "tau_21": ("21-cm optical depth", "YlGnBu", "log"),
    "cumulative_recombinations": ("Recombinations", "Reds_r", "lin"),
    "ionisation_rate_G12": ("Ionising background", "viridis", "log"),
    "mean_free_path": ("Mean free path", "viridis", "log"),
    "z_reion": ("Reionisation redshift", "plasma", "zreion"),
}


def colour(q, vals):
    """RGB (0..1) for the values of one quantity; non-finite values are black."""
    _, cmap, scale = SPEC.get(q, (q, "viridis", "lin"))
    cm = colormaps[cmap] if isinstance(cmap, str) else cmap
    ok = np.isfinite(vals)
    data = vals.astype(np.float64)
    if scale == "unit":
        norm = colors.Normalize(0, 1)
    elif scale == "eor":
        norm = colors.Normalize(-150, 30)
    elif scale == "log1p":
        data = np.log10(np.clip(1 + data, 1e-3, None))
        lo, hi = np.percentile(data[ok], [1, 99.5]) if ok.any() else (0, 1)
        norm = colors.Normalize(lo, hi if hi > lo else lo + 1)
    elif scale in ("log", "zreion"):
        pos = data[ok & (data > 0)]
        lo, hi = np.percentile(pos, [2, 99.8]) if pos.size else (1, 10)
        hi = max(hi, lo * (1 + 1e-6))
        if scale == "zreion":
            ok &= data > 0
            norm = colors.Normalize(lo, hi)
        else:
            data = np.log10(np.clip(data, lo, None))
            norm = colors.Normalize(np.log10(lo), np.log10(hi))
    else:
        lo, hi = np.percentile(data[ok], [1, 99.5]) if ok.any() else (0, 1)
        norm = colors.Normalize(lo, hi if hi > lo else lo + 1)
    rgb = cm(norm(np.where(ok, data, 0)))[..., :3].astype(np.float32)
    rgb[~ok] = 0
    return rgb


def read_rows(ds, rows, k0, k1):
    """ds[rows, k0:k1] for sorted row indices, read as contiguous runs."""
    breaks = np.nonzero(np.diff(rows) != 1)[0] + 1
    return np.concatenate([ds[r[0]:r[-1] + 1, k0:k1] for r in np.split(rows, breaks)], axis=0)


# ---------------------------------------------------------------- the sectors
nq = len(args.quantities)
edges = np.linspace(-180, 180, nq + 1)
half = 180 / nq
BLEND = 1.2                                            # width of the seams [deg]
win = min(180.0, half + 3 * BLEND)
k0 = max(0, int(np.searchsorted(dist, d_of_z(zmin))) - 1)
k1 = min(dist.size, int(np.searchsorted(dist, d_of_z(zmax))) + 1)
img = np.zeros((N, N, 3), np.float32)
wsum = np.zeros((N, N), np.float32)
t0 = time.perf_counter()
for i, q in enumerate(args.quantities):
    mid = 0.5 * (edges[i] + edges[i + 1])
    dth_pix = (TH - mid + 180) % 360 - 180
    sel = ring & (np.abs(dth_pix) <= win)
    pix = np.flatnonzero(sel)

    # the lightcone samples of this sector, ordered by angle
    rel = (np.degrees(lon) - mid + 180) % 360 - 180
    rows = np.flatnonzero(np.abs(rel) <= win + 360 / n_lon)
    block = read_rows(f["lightcones"][q], rows, k_lo + k0, k_lo + k1).astype(np.float64)
    order = np.argsort(rel[rows])
    rel_s, block = rel[rows][order], block[order]
    d_s = dist[k0:k1]

    # mean of the samples that land in each page pixel
    th = np.radians(rel_s + mid)[:, None]
    r_s = r_of_z(z_of_d(d_s))[None, :]
    x, y = r_s * np.sin(th), r_s * np.cos(th)
    u, v = disc_to_square(x, y) if stretch else (x, y)
    ix = np.clip(((u + 1) / 2 * N).astype(np.int64), 0, N - 1)
    iy = np.clip(((1 - v) / 2 * N).astype(np.int64), 0, N - 1)
    flat = (iy * N + ix).ravel()
    del x, y, u, v, ix, iy
    total = np.bincount(flat, weights=block.ravel(), minlength=N * N)[pix]
    count = np.bincount(flat, minlength=N * N)[pix]
    del flat
    vals = np.where(count > 0, total / np.maximum(count, 1), np.nan)

    # pixels no sample landed in: bilinear sample of the lightcone
    need = count == 0
    if need.any():
        ia = np.interp(dth_pix.ravel()[pix[need]], rel_s, np.arange(rel_s.size))
        ib = np.interp(D_pix.ravel()[pix[need]], d_s, np.arange(d_s.size))
        vals[need] = map_coordinates(block, [ia, ib], order=1, mode="nearest")

    w = 1 / (1 + np.exp((np.abs(dth_pix.ravel()[pix]) - half) / (BLEND / 4)))
    img.reshape(-1, 3)[pix] += colour(q, vals) * w[:, None].astype(np.float32)
    wsum.ravel()[pix] += w
    log.info(f"{q}: {rows.size} longitudes x {d_s.size} slices onto {pix.size} pixels, "
             f"{need.mean():.0%} by interpolation ({time.perf_counter() - t0:.0f} s)")
f.close()
img /= np.maximum(wsum, 1e-6)[..., None]
img[~ring] = 0
del TH, D_pix, wsum

# ---------------------------------------------------------------- figure
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

s = N / args.dpi / 10                                  # font scale (the mock-up was 10 in wide)
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": "w"})
fig = plt.figure(figsize=(N / args.dpi, N / args.dpi), facecolor="black")
ax = fig.add_axes([0, 0, 1, 1])
ax.axis("off")
ax.imshow((np.clip(img, 0, 1) * 255).astype(np.uint8), extent=[-1, 1, -1, 1], interpolation="nearest")
del img
ax.set_xlim(-1, 1)
ax.set_ylim(-1, 1)
to_page = disc_to_square if stretch else (lambda x, y: (x, y))
ph = np.linspace(0, 2 * np.pi, 720)
xs, ys = to_page(R_IN * np.sin(ph), R_IN * np.cos(ph))
ax.fill(xs, ys, color="black", zorder=3)
if not args.no_text:
    ax.plot(xs, ys, color="#ffd54f", lw=1.4 * s, zorder=4)
    if args.order == "lowz_in":
        ax.plot(0, 0, "*", color="#ffd54f", ms=12 * s, zorder=5)
    box = dict(fc="black", alpha=0.5, ec="none", pad=0.8 * s)
    for z in (6, 7, 8, 10, 12, 15, 20, 30):
        if not zmin < z < zmax:
            continue
        q_r = r_of_z(z)
        xs, ys = to_page(q_r * np.sin(ph), q_r * np.cos(ph))
        ax.plot(xs, ys, color="w", lw=0.6 * s, alpha=0.4, zorder=2)
        a = np.radians(-45)
        lx, ly = to_page(q_r * np.sin(a), q_r * np.cos(a))
        ax.text(lx, ly, f"z={z:g}", size=7.5 * s, ha="center", va="center", rotation=45, bbox=box, zorder=4)
    for i, q in enumerate(args.quantities):
        name = SPEC.get(q, (q,))[0]
        mid = 0.5 * (edges[i] + edges[i + 1])
        a = np.radians(mid)
        if stretch:
            lx, ly = to_page(0.8 * np.sin(a), 0.8 * np.cos(a))
            ax.text(lx, ly, name, ha="center", va="center", size=10 * s, weight="bold", zorder=4,
                    bbox=dict(fc="black", alpha=0.45, ec="none", pad=1.5 * s))
        else:
            rot = -mid if abs(mid) <= 90 else 180 - mid
            ax.text((R_OUT + 0.035) * np.sin(a), (R_OUT + 0.035) * np.cos(a), name, ha="center", va="center",
                    size=10 * s, weight="bold", rotation=rot, zorder=4)
    title = "EOS26" if args.production else f"EOS26 test · HII_DIM = {run.n}"
    ax.text(-0.975, 0.975, title, size=(22 if args.production else 14) * s, weight="bold", family="serif",
            ha="left", va="top", zorder=4, bbox=dict(fc="black", alpha=0.45, ec="none", pad=2 * s))
    inner, outer = (zmin, zmax) if args.order == "lowz_in" else (zmax, zmin)
    note = (f"21cmFAST {version} · angular lightcone around an observer at the box centre · "
            f"z = {inner:g} (centre) → {outer:g} (rim), radius ∝ "
            f"{'cosmic time' if args.radius == 'time' else 'comoving distance'}"
            + (" · stretched onto the square, not to scale" if stretch else ""))
    ax.text(-0.975, -0.975, note, ha="left", va="bottom", size=7 * s, color="0.85", zorder=4,
            bbox=dict(fc="black", alpha=0.6, ec="none", pad=1.5 * s))

tags = ("_circle" if args.circle else "") + ("_hiz_in" if args.order == "hiz_in" else "") \
    + ("_distance" if args.radius == "distance" else "") + ("_notext" if args.no_text else "")
out = Path(args.out or eb.PLOTS / f"lightcone_square_{run.tag}_v{version}{tags}.png")
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out, dpi=args.dpi, facecolor="black")
log.info(f"Saved {out} ({N} x {N} px, {time.perf_counter() - t0:.0f} s)")
