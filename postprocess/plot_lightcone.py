import gc
gc.collect()
gc.disable()

import time
from pathlib import Path
import argparse
import sys
sys.path.insert(1, 'run_scripts/')
import settings

# Parse args and set up logging BEFORE other imports
parser = argparse.ArgumentParser()
settings.add_common_args(parser)

args = parser.parse_args()
logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache

import numpy as np
import matplotlib.pyplot as plt

from matplotlib import rcParams
rcParams.update({"font.size":20, "font.family": 'serif'})
from matplotlib import colormaps, colors, ticker

eor_colour = colors.LinearSegmentedColormap.from_list(
    "EoR",
    [
        (0, "white"),
        (0.21, "yellow"),
        (0.42, "orange"),
        (0.63, "red"),
        (0.86, "black"),
        (0.9, "blue"),
        (1, "cyan"),
    ],
)
try:
    colormaps.register(cmap=eor_colour)
except:
    pass

job_start = time.perf_counter()
logger.info(f"Starting lightcone plotting")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _input_overrides = settings.inputs_for_run(args.test, args.compare)

cache = p21c.OutputCache(cache_dir)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **_input_overrides)
HII_DIM = inputs.simulation_options.HII_DIM
BOX_LEN = inputs.simulation_options.BOX_LEN

plotspath = Path("plots")
plotspath.mkdir(exist_ok=True)
lc_path = settings.lightcone_path(cache_dir)
lightcone = p21c.LightCone.from_file(lc_path)
logger.info(f"Read {lc_path}: {sorted(lightcone.lightcones)}")

# label, colour map, scale. Scales: lin (5-95th percentile), log (positive values,
# 5-99.5th percentile; zeros shown grey), sym (symmetric about 0), eor (fixed -150..30
# mK), unit (0..1), zreion (only reionised cells).
SPEC = {
    "density": (r"$\delta$", "viridis", "lin"),
    "velocity_z": (r"$v_z$", "RdBu_r", "sym"),
    "brightness_temp": (r"$\delta T_{21}$ [mK]", "EoR", "eor"),
    "tau_21": (r"$\tau_{21}$", "YlGnBu", "log"),
    "spin_temperature": (r"$T_S$ [K]", "inferno", "log"),
    "kinetic_temp_neutral": (r"$T_K$ [K]", "magma", "log"),
    "xray_ionised_fraction": (r"$x_e$", "cividis", "log"),
    "J_21_LW": (r"$J_{21,LW}$", "Blues", "log"),
    "neutral_fraction": (r"$x_{HI}$", "hot", "unit"),
    "cumulative_recombinations": ("cumul. recombs", "Reds", "lin"),
    "z_reion": (r"$z_{reion}$", "plasma", "zreion"),
    "ionisation_rate_G12": (r"$\Gamma_{12}$", "viridis", "log"),
    "sfrd_acg": (r"SFRD (ACG)", "magma", "log"),
    "sfrd_mcg": (r"SFRD (MCG)", "magma", "log"),
    "xray_emissivity": (r"X-ray emissivity", "inferno", "log"),
    "n_ion": (r"$n_{ion}$", "viridis", "log"),
    "fesc_weighted_sfrd": (r"$f_{esc}$-weighted SFRD", "magma", "log"),
}


def _norm(data, scale):
    """Colour normalisation and the (masked) data to draw."""
    finite = data[np.isfinite(data)]
    if scale == "eor":
        return colors.Normalize(-150, 30), data
    if scale == "unit":
        return colors.Normalize(0, 1), data
    if scale == "sym":
        v = np.nanpercentile(np.abs(finite), 99) if finite.size else 1
        return colors.Normalize(-v, v), data
    if scale in ("log", "zreion"):
        positive = finite[finite > 0]
        masked = np.ma.masked_where(~(data > 0), data)
        if positive.size == 0:
            return colors.Normalize(0, 1), masked
        lo, hi = np.percentile(positive, [5, 99.5])
        if scale == "zreion" or hi < 30 * lo:  # less than ~1.5 decades: linear reads better
            return colors.Normalize(lo, max(hi, lo * (1 + 1e-6))), masked
        return colors.LogNorm(lo, hi), masked
    lo, hi = (np.percentile(finite, [5, 95]) if finite.size else (0, 1))
    return colors.Normalize(lo, hi if hi > lo else lo + 1), data


keys = [k for k in SPEC if k in lightcone.lightcones] + sorted(k for k in lightcone.lightcones if k not in SPEC)
ncols = min(len(keys), 6)
nrows = int(np.ceil(len(keys) / ncols))
fig, axs = plt.subplots(nrows=nrows, ncols=ncols, sharey=True, figsize=(4 * ncols, 14 * nrows), squeeze=False)
x = np.linspace(0, BOX_LEN, HII_DIM)
z = lightcone.lightcone_redshifts
for ax, k in zip(axs.flat, keys):
    label, cmap_name, scale = SPEC.get(k, (k, "viridis", "lin"))
    cmap = colormaps[cmap_name].copy()
    cmap.set_bad("lightgrey")
    data = np.asarray(lightcone.lightcones[k][0, ...], dtype=float)
    norm, shown = _norm(data, scale)
    im = ax.pcolormesh(x, z, shown.T, norm=norm, cmap=cmap, shading="auto")
    cb = plt.colorbar(im, orientation="horizontal", ax=ax, label=label, pad=0.07)
    if isinstance(norm, colors.LogNorm):
        cb.ax.xaxis.set_major_locator(ticker.LogLocator(numticks=4))
        cb.ax.xaxis.set_minor_formatter(ticker.NullFormatter())
    else:
        cb.ax.xaxis.set_major_locator(ticker.MaxNLocator(3))
    ax.set_yscale("log")
    ax.set_xlabel("Mpc", labelpad=1)
for ax in axs.flat[len(keys):]:
    ax.set_visible(False)
for row in axs:
    row[0].set_ylabel("Redshift")
tag = f"test_HIIDIM{HII_DIM}" if args.test else "EOS26"
out = plotspath / f"lightcones_{tag}_v{p21c.__version__}.png"
plt.savefig(out, bbox_inches="tight", dpi=100)
logger.info(f"Saved {len(keys)} lightcones to {out}")
