"""Read thin slabs of the boxes of an EOS26 run straight from its cache.

The plot scripts in postprocess/ only need one plane of each box (a slice, or one
plane per redshift for a lightcone). Loading the boxes through py21cmfast reads the
whole array (13.5 GB per field at HII_DIM=1500), so this reads the plane with h5py
instead: box[x0:x0+width, :, :] is contiguous on disk (9 MB per cell of width at 1500).

    run = Run(test=False)                     # production cache (settings.py)
    run.path("PerturbedField", z=15.1)        # cached file of a box, None if missing
    read_plane(path, "density", x0=0)         # (HII_DIM, HII_DIM * NON_CUBIC_FACTOR)
    halo_planes(run, z, ["stellar_mass"])     # halo properties summed onto the plane
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "run_scripts"))
import settings  # noqa: E402

log = logging.getLogger("21cmFAST")
PLOTS = Path(__file__).resolve().parents[1] / "plots"

# quantity -> the cached output struct (h5 file) that holds it
FIELD_KIND = {
    "density": "PerturbedField",
    "velocity_x": "PerturbedField",
    "velocity_y": "PerturbedField",
    "velocity_z": "PerturbedField",
    "brightness_temp": "BrightnessTemp",
    "tau_21": "BrightnessTemp",
    "spin_temperature": "TsBox",
    "kinetic_temp_neutral": "TsBox",
    "xray_ionised_fraction": "TsBox",
    "J_21_LW": "TsBox",
    "neutral_fraction": "IonizedBox",
    "z_reion": "IonizedBox",
    "ionisation_rate_G12": "IonizedBox",
    "cumulative_recombinations": "IonizedBox",
    "kinetic_temperature": "IonizedBox",
    "mean_free_path": "IonizedBox",
    "sfrd_acg": "EmissivityFields",
    "sfrd_mcg": "EmissivityFields",
    "xray_emissivity": "EmissivityFields",
    "n_ion": "EmissivityFields",
    "fesc_weighted_sfrd": "EmissivityFields",
}
# quantity from the halo catalogues -> per-halo properties summed per cell
# (columns of 21cmFAST's test_halo_props, as in cfuncs.convert_halo_properties)
HALO_QUANTITIES = {
    "halo_mass": ("halo_mass",),
    "stellar_mass": ("stellar_mass_acg", "stellar_mass_mcg"),
    "stellar_mass_acg": ("stellar_mass_acg",),
    "stellar_mass_mcg": ("stellar_mass_mcg",),
    "sfr": ("sfr_acg", "sfr_mcg"),
    "sfr_acg": ("sfr_acg",),
    "sfr_mcg": ("sfr_mcg",),
}
SECONDS_PER_YEAR = 3.15576e7
_HALO_PROPS = ("halo_mass", "stellar_mass_acg", "sfr_acg", "xray_luminosity", "n_ion",
               "fesc_weighted_sfr", "stellar_mass_mcg", "sfr_mcg", "mturn_acg", "mturn_mcg",
               "metallicity_acg")


def source_kind(quantity: str) -> str:
    if quantity in HALO_QUANTITIES:
        return "HaloCatalog"
    if quantity in FIELD_KIND:
        return FIELD_KIND[quantity]
    raise KeyError(f"unknown quantity {quantity!r}; known: {sorted(FIELD_KIND) + sorted(HALO_QUANTITIES)}")


class Run:
    """The inputs and cached box files of the production run (or of the test reference)."""

    def __init__(self, test: bool = False, compare: bool = False):
        import py21cmfast as p21c
        from py21cmfast.io.caching import RunCache

        self.test = test
        self.cache_dir, overrides = settings.inputs_for_run(test, compare)
        self.inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
        self.rc = RunCache.from_inputs(self.inputs, cache=p21c.OutputCache(self.cache_dir))
        so = self.inputs.simulation_options
        self.n = int(so.HII_DIM)
        self.n_los = int(round(so.NON_CUBIC_FACTOR * so.HII_DIM))
        self.cell = float(so.BOX_LEN) / so.HII_DIM  # Mpc
        self.tag = f"test_HIIDIM{self.n}" if test else "EOS26"
        self.version = p21c.__version__
        self.redshifts = sorted(float(z) for z in self.inputs.node_redshifts)

    def nearest_z(self, z: float) -> float:
        return min(self.redshifts, key=lambda zz: abs(zz - z))

    def path(self, kind: str, z: float | None = None) -> Path | None:
        """The cached file of a box (None if it isn't there yet)."""
        if kind == "InitialConditions":
            p = Path(self.rc.InitialConditions)
        else:
            files = getattr(self.rc, kind)
            key = min(files, key=lambda zz: abs(zz - z))
            if abs(key - z) > 1e-3:
                return None
            p = Path(files[key])
        return p if p.exists() else None


def read_plane(path: Path, kind: str, field: str, x0: int = 0, width: int = 1) -> np.ndarray:
    """Mean of box[x0:x0+width, :, :] of one field of a cached box, as float32."""
    with h5py.File(path, "r") as f:
        ds = f[f"{kind}/OutputFields/{field}"]
        return np.asarray(ds[x0:x0 + width], dtype=np.float32).mean(axis=0)


def has_field(path: Path, kind: str, field: str) -> bool:
    with h5py.File(path, "r") as f:
        return f"{kind}/OutputFields/{field}" in f


def _read_halos_in_slab(path: Path, lo: float, hi: float, chunk: int = 20_000_000) -> dict:
    """The halos of a HaloCatalog with lo <= x < hi [Mpc], read in chunks."""
    keys = ("halo_masses", "star_rng", "sfr_rng", "xray_rng")
    parts = {k: [] for k in ("halo_coords", *keys)}
    with h5py.File(path, "r") as f:
        g = f["HaloCatalog/OutputFields"]
        n = g["halo_masses"].shape[0]
        for a in range(0, n, chunk):
            c = g["halo_coords"][a:a + chunk]
            m = (c[:, 0] >= lo) & (c[:, 0] < hi)
            if not m.any():
                continue
            parts["halo_coords"].append(c[m])
            for k in keys:
                parts[k].append(g[k][a:a + chunk][m])
    out = {k: (np.concatenate(v) if v else np.zeros((0, 3) if k == "halo_coords" else 0, np.float32))
           for k, v in parts.items()}
    out["n_total"] = n
    return out


def _halo_properties(run: Run, z: float, halos: dict, x0: int, width: int) -> tuple[dict, bool]:
    """Per-halo properties from 21cmFAST's own scaling relations (lib.test_halo_props).

    Like cfuncs.convert_halo_properties, but the feedback grids it needs (v_cb, J_21_LW,
    z_reion, Gamma_12; HII_DIM^3 each) are filled only on the planes x0..x0+width that
    the selected halos sit in; the rest is left as untouched zero pages. Feedback is
    taken from the previous node redshift (as in the simulation's step) when its
    TsBox/IonizedBox is cached; otherwise there is none (bool returned).
    """
    from py21cmfast.c_21cmfast import ffi, lib
    from py21cmfast.drivers._global_initialization import c_state

    shape = (run.n, run.n, run.n_los)
    zeros = np.zeros(shape, np.float32)  # never written: zero pages, no real memory
    grids = {"vcb": np.zeros(shape, np.float32), "J21": zeros, "zre": zeros, "G12": zeros}
    sl = slice(x0, x0 + width)
    ics = run.path("InitialConditions")
    if ics is not None and has_field(ics, "InitialConditions", "lowres_vcb"):
        with h5py.File(ics, "r") as f:
            grids["vcb"][sl] = f["InitialConditions/OutputFields/lowres_vcb"][sl]
    higher = [zz for zz in run.redshifts if zz > z + 1e-6]
    feedback = False
    if higher:
        zp = higher[0]
        ts, ion = run.path("TsBox", zp), run.path("IonizedBox", zp)
        if ts is not None and ion is not None:
            grids.update({k: np.zeros(shape, np.float32) for k in ("J21", "zre", "G12")})
            with h5py.File(ts, "r") as f:
                grids["J21"][sl] = f["TsBox/OutputFields/J_21_LW"][sl]
            with h5py.File(ion, "r") as f:
                grids["zre"][sl] = f["IonizedBox/OutputFields/z_reion"][sl]
                grids["G12"][sl] = f["IonizedBox/OutputFields/ionisation_rate_G12"][sl]
            feedback = True
    n = halos["halo_masses"].size
    out = np.zeros((n, len(_HALO_PROPS)), np.float32)
    arr = {k: np.ascontiguousarray(halos[k], dtype=np.float32)
           for k in ("halo_masses", "halo_coords", "star_rng", "sfr_rng", "xray_rng")}
    if n:
        # test_halo_props needs the power spectrum set up (ps=True). 4.3.1's
        # convert_halo_properties only broadcasts the inputs, and segfaults.
        with c_state(run.inputs, broadcast_inputs=True, ps=True):
            lib.test_halo_props(
                z,
                *(ffi.cast("float *", grids[k].ctypes.data) for k in ("vcb", "J21", "zre", "G12")),
                n,
                *(ffi.cast("float *", arr[k].ctypes.data)
                  for k in ("halo_masses", "halo_coords", "star_rng", "sfr_rng", "xray_rng")),
                ffi.cast("float *", out.ctypes.data),
            )
    return {k: out[:, i] for i, k in enumerate(_HALO_PROPS)}, feedback


def halo_planes(run: Run, z: float, quantities, x0: int = 0, width: int = 1) -> tuple[dict, bool]:
    """Halo quantities summed per cell of the plane x0..x0+width, per Mpc^3.

    Masses in M_sun Mpc^-3, star formation rates in M_sun yr^-1 Mpc^-3 (21cmFAST's are
    per second).
    """
    path = run.path("HaloCatalog", z)
    halos = _read_halos_in_slab(path, x0 * run.cell, (x0 + width) * run.cell)
    props, feedback = _halo_properties(run, z, halos, x0, width)
    c = halos["halo_coords"]
    iy = np.minimum((c[:, 1] / run.cell).astype(np.int64), run.n - 1)
    iz = np.minimum((c[:, 2] / run.cell).astype(np.int64), run.n_los - 1)
    flat = iy * run.n_los + iz
    vol = run.cell ** 3 * width
    planes = {}
    for q in quantities:
        w = sum(props[p] for p in HALO_QUANTITIES[q]).astype(np.float64)
        if q.startswith("sfr"):
            w *= SECONDS_PER_YEAR
        planes[q] = (np.bincount(flat, weights=w, minlength=run.n * run.n_los)
                     .reshape(run.n, run.n_los) / vol).astype(np.float32)
    log.info(f"z={z:.3f}: {halos['halo_masses'].size} of {halos['n_total']} halos in the slab"
             f"{'' if feedback else ' (no feedback grids yet)'}")
    return planes, feedback


def slice_figure(plane, box_len, out, *, title, label, vel=None, zoom=None, cmap="RdBu_r", vmax=None):
    """Save a plane (rows: y, columns: z of the box) as an image, optionally with arrows.

    vel: (v_y, v_z) planes of the same shape; zoom: show only the first zoom x zoom cells.
    The colour scale is symmetric about 0 (|values| up to the 99.5th percentile, or vmax).
    """
    import matplotlib.pyplot as plt

    n_y, n_z = plane.shape
    cell = box_len / n_y
    if zoom:
        plane = plane[:zoom, :zoom]
        vel = None if vel is None else tuple(v[:zoom, :zoom] for v in vel)
    ext = [0, plane.shape[1] * cell, 0, plane.shape[0] * cell]
    vmax = vmax or float(np.nanpercentile(np.abs(plane), 99.5)) or 1.0
    fig, ax = plt.subplots(figsize=(7, 6), layout="constrained")
    im = ax.imshow(plane, origin="lower", extent=ext, cmap=cmap, vmin=-vmax, vmax=vmax,
                   interpolation="nearest")
    fig.colorbar(im, ax=ax, label=label, shrink=0.85)
    if vel is not None:
        step = max(1, plane.shape[0] // 40)
        yy, zz = np.mgrid[0:plane.shape[0]:step, 0:plane.shape[1]:step]
        ax.quiver((zz + 0.5) * cell, (yy + 0.5) * cell, vel[1][::step, ::step], vel[0][::step, ::step],
                  color="k", alpha=0.7, width=0.002)
    ax.set_xlabel("z [Mpc]")
    ax.set_ylabel("y [Mpc]")
    ax.set_title(title, fontsize=10)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    log.info(f"Saved {out}")
