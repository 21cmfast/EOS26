"""Lightcones of one quantity, built straight from the cached coevals of a run.

The library behind postprocess/lightcone/ (README.md there). One pass over the node
redshifts reads the quantity's box at each redshift once and fills any number of
lightcone geometries from it:

* Rect     21cmFAST's RectilinearLightconer: the line of sight along the box's last axis,
           (HII_DIM, HII_DIM, n_slices).
* Angular  arbitrary directions seen from an origin, with the box tiled periodically:
           the ring of postprocess/make_angular_lightcone.py (n_lon, n_slices), or a
           full-sky HEALPix map per shell (n_shells, n_pix).

Slices, distances and the interpolation between the two bracketing node redshifts are
those of 21cmFAST 4.3.1's run_lightcone (Lightconer.make_lightcone_slices), with two
differences that change the cost, not the result:

* Only the requested field is read (run_lightcone reads every field of every struct,
  for its global means), so one quantity costs one 13.5 GB read per node redshift at
  HII_DIM=1500.
* Angular slices sample the two bracketing boxes at the pixels and interpolate those
  samples in distance. 21cmFAST interpolates the whole box in distance for every slice
  before sampling it (~20 s per slice at 1500^3). Both steps are linear, so the result
  is the same to rounding. z_reion's "mean_max" rule is per cell, so for it the rule is
  applied at the 8 cells around each sample point before weighting them.

The special quantity "los_velocity" is the line-of-sight velocity that 21cmFAST adds for
the dv/dr correction of the brightness temperature (velocity_z for Rect; the projection
of velocity_x/y/z on the line of sight, positive towards the observer, for Angular).

Every output file records which node intervals are done, so a killed job resumes.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import h5py
import numpy as np
from astropy import units
from scipy.ndimage import map_coordinates

log = logging.getLogger("21cmFAST")

FORMAT = "EOS26 lightcone v1"
LOS_VELOCITY = "los_velocity"
VELOCITIES = ("velocity_x", "velocity_y", "velocity_z")
# 21cmFAST's Lightconer.interp_kinds default; everything else is "mean"
INTERP_KIND = {"z_reion": "mean_max"}


# ── the run: fields and cached files ────────────────────────────────────────


def field_kinds(inputs) -> dict[str, str]:
    """Coeval field -> name of the cached output struct (h5 file) that holds it.

    Taken from 21cmFAST itself, like LightCone.get_fields: every array of PerturbedField,
    EmissivityFields, IonizedBox, BrightnessTemp and (with USE_TS_FLUCT) TsBox.
    """
    from py21cmfast.wrapper import outputs as o

    structs = [o.PerturbedField, o.EmissivityFields, o.IonizedBox, o.BrightnessTemp]
    if inputs.astro_options.USE_TS_FLUCT:
        structs.append(o.TsBox)
    kinds = {}
    for cls in structs:
        for name in cls.new(inputs, redshift=0).arrays:
            kinds.setdefault(name, cls.__name__)
    return kinds


class CachePaths:
    """The cached file of each output struct at each node redshift of a run."""

    def __init__(self, inputs, cache_dir: str | Path):
        import py21cmfast as p21c
        from py21cmfast.io.caching import RunCache

        self.cache_dir = Path(cache_dir)
        self.rc = RunCache.from_inputs(inputs, cache=p21c.OutputCache(str(cache_dir)))

    def path(self, kind: str, z: float) -> Path | None:
        files = getattr(self.rc, kind)
        key = min(files, key=lambda zz: abs(zz - z))
        if abs(key - z) > 1e-3:
            return None
        p = Path(files[key])
        return p if p.exists() else None


def source_fields(quantity: str, geometries) -> list[str]:
    """The coeval fields one quantity needs (three velocities for an angular los_velocity)."""
    if quantity != LOS_VELOCITY:
        return [quantity]
    if any(isinstance(g, Angular) for g in geometries):
        return list(VELOCITIES)
    return ["velocity_z"]


def read_box(path: Path, kind: str, field: str, out: np.ndarray | None = None) -> np.ndarray:
    """One field of a cached box as float32, into ``out`` if it has the right shape."""
    with h5py.File(path, "r") as f:
        ds = f[f"{kind}/OutputFields/{field}"]
        if out is None or out.shape != ds.shape:
            out = np.empty(ds.shape, np.float32)
        ds.read_direct(out)
    return out


def interpolate(v1, v2, d, d1, d2, kind: str = "mean") -> np.ndarray:
    """21cmFAST's Lightconer.redshift_interpolation, with d broadcast over the last axis.

    v1 is at distance d1 (the lower redshift), v2 at d2. Computed in float64 like
    21cmFAST (whose distances are float64 Quantities).
    """
    a = np.asarray(v1, dtype=np.float64)
    b = np.asarray(v2, dtype=np.float64)
    out = (np.abs(d2 - d) * a + np.abs(d1 - d) * b) / np.abs(d1 - d2)
    if kind == "mean_max":
        flag = v1 * v2 < 0
        out[flag] = np.maximum(v1, v2)[flag]
    elif kind != "mean":
        raise ValueError("kind must be 'mean' or 'mean_max'")
    return out


# ── geometries ──────────────────────────────────────────────────────────────


class Geometry:
    """Distances of the slices (Mpc), and how one quantity is sampled at them."""

    name: str

    def __init__(self, inputs, lc_distances: units.Quantity):
        so = inputs.simulation_options
        self.cosmo = inputs.cosmo_params.cosmo
        self.cell = so.cell_size  # Quantity, Mpc
        self.lc_distances = lc_distances.to(units.Mpc)
        eq = units.pixel_scale(self.cell / units.pixel)
        self.lcpix = self.lc_distances.to(units.pixel, eq).value
        dmin = self.cosmo.comoving_distance(min(inputs.node_redshifts))
        dmax = self.cosmo.comoving_distance(max(inputs.node_redshifts))
        if not (dmin <= self.lc_distances.min() and self.lc_distances.max() <= dmax):
            raise ValueError("lightcone distances outside the range of the node redshifts")

    @property
    def n_slices(self) -> int:
        return len(self.lc_distances)

    def lc_redshifts(self) -> np.ndarray:
        from astropy.cosmology import z_at_value

        zmin = z_at_value(self.cosmo.comoving_distance, self.lc_distances.min()).value
        zmax = z_at_value(self.cosmo.comoving_distance, self.lc_distances.max()).value
        zgrid = np.logspace(np.log10(zmin), np.log10(zmax), 100)
        dgrid = self.cosmo.comoving_distance(zgrid)
        return np.interp(self.lc_distances.value, dgrid.value, zgrid)

    # file layout
    def dataset_shape(self) -> tuple[int, ...]:
        raise NotImplementedError

    def chunks(self) -> tuple[int, ...]:
        raise NotImplementedError

    def attrs(self) -> dict:
        return {}

    def write(self, ds, idx: np.ndarray, block: np.ndarray) -> None:
        """Write the slices idx (block's last axis) into the output dataset."""
        raise NotImplementedError

    def fill(self, ds, idx, lcd, fields1, fields2, d1, d2, kind, threads) -> None:
        raise NotImplementedError


class Rect(Geometry):
    """21cmFAST's RectilinearLightconer (line of sight = the box's last axis)."""

    name = "rect"

    def __init__(self, inputs, min_redshift: float, max_redshift: float):
        import py21cmfast as p21c

        so = inputs.simulation_options
        self.lightconer = p21c.RectilinearLightconer.between_redshifts(
            min_redshift=min_redshift,
            max_redshift=max_redshift,
            resolution=so.cell_size,
            cosmo=inputs.cosmo_params.cosmo,
        )
        super().__init__(inputs, self.lightconer.lc_distances)
        self.n = int(so.HII_DIM)
        self.n_los = int(round(so.NON_CUBIC_FACTOR * so.HII_DIM))
        self.index_offset = int(self.lightconer.index_offset)
        lcpix = self.lightconer.get_lc_distances_in_pixels(self.cell)
        self._lcpix_max = lcpix.max()

    def plane_index(self, lcd: units.Quantity) -> int:
        # RectilinearLightconer.coeval_subselect (take with mode="wrap")
        lcidx = int((self._lcpix_max - lcd + 1 * units.pixel).to_value(units.pixel))
        return -lcidx + self.index_offset

    def dataset_shape(self):
        return (self.n, self.n, self.n_slices)

    def chunks(self):
        return (min(128, self.n), self.n, 1)

    def attrs(self):
        return {"index_offset": self.index_offset, "line_of_sight_axis": -1}

    def fill(self, ds, idx, lcd, fields1, fields2, d1, d2, kind, threads):
        planes = [self.plane_index(d) for d in lcd]
        # los_velocity is velocity_z for Rect (the last of VELOCITIES when Angular
        # geometries in the same pass made all three be read)
        b1, b2 = fields1[-1], fields2[-1]
        if len(fields1) not in (1, 3):
            raise ValueError("expected one field or the three velocities")
        p1 = np.take(b1, planes, axis=2, mode="wrap")
        p2 = np.take(b2, planes, axis=2, mode="wrap")
        d = np.array([x.value for x in lcd])
        block = interpolate(p1, p2, d, d1, d2, kind).astype(np.float32)
        ds[:, :, idx[0]: idx[-1] + 1] = block


class Angular(Geometry):
    """Samples along directions (latitude, longitude) seen from ``origin`` (pixels).

    Like 21cmFAST's AngularLightconer (cosmotile's interpolator: map_coordinates,
    order 1, mode "grid-wrap", no prefilter, no rotation). With ``n_sub`` > 1 every
    output pixel is the mean of n_sub consecutive directions (its HEALPix children).
    """

    name = "angular"
    shell_major = False  # (n_pix, n_slices) like 21cmFAST; HEALPix: (n_slices, n_pix)

    def __init__(self, inputs, lc_distances, latitude, longitude, origin, n_sub=1,
                 chunk=1 << 20, unit_dtype=np.float64):
        super().__init__(inputs, lc_distances)
        self.origin = np.asarray(origin, dtype=np.float64)
        self.n_sub = int(n_sub)
        self.n_dir = len(latitude)
        if self.n_dir % self.n_sub:
            raise ValueError("number of directions must be a multiple of n_sub")
        self.n_pix = self.n_dir // self.n_sub
        # chunks of whole output pixels
        self.chunk = max(self.n_sub, (chunk // self.n_sub) * self.n_sub)
        self.unit = self._unit_vectors(latitude, longitude, unit_dtype)
        self.out_index = None  # optional permutation applied to each output map

    @staticmethod
    def _unit_vectors(latitude, longitude, dtype, block=1 << 24):
        # cosmotile.transform_to_pixel_coords without the radius
        unit = np.empty((3, len(latitude)), dtype=dtype)
        for a in range(0, len(latitude), block):
            lat = np.asarray(latitude[a:a + block], dtype=np.float64)
            lon = np.asarray(longitude[a:a + block], dtype=np.float64)
            phi = np.pi / 2 - lat
            sinphi = np.sin(phi)
            unit[0, a:a + block] = sinphi * np.cos(lon)
            unit[1, a:a + block] = sinphi * np.sin(lon)
            unit[2, a:a + block] = np.cos(phi)
        return unit

    def _coords(self, r: float, sl: slice) -> np.ndarray:
        u = self.unit[:, sl]
        if u.dtype != np.float64:
            u = u.astype(np.float64)
        c = r * u
        c += self.origin[:, None]
        return c

    def sample_pair(self, fields1, fields2, r, d1, d2, kind, threads) -> np.ndarray:
        """The interpolated value of each output pixel on the shell at r (pixels)."""
        out = np.empty(self.n_pix, dtype=np.float64)
        vector = len(fields1) == 3

        def work(a):
            sl = slice(a, min(a + self.chunk, self.n_dir))
            coords = self._coords(r, sl)

            def sample(box):
                return map_coordinates(box, coords, order=1, mode="grid-wrap",
                                       prefilter=False, output=np.float64)

            if kind == "mean_max":
                # a per-cell rule: apply it at the 8 cells around each point, then
                # weight them, which is what sampling 21cmFAST's interpolated box gives
                v = _trilinear_merged(fields1[0], fields2[0], coords, r, d1, d2)
            else:
                if vector:
                    # line-of-sight component, positive towards the observer
                    # (cosmotile.make_lightcone_slice_vector_field)
                    u = self.unit[:, sl].astype(np.float64, copy=False)
                    v1 = -sum(sample(b) * u[i] for i, b in enumerate(fields1))
                    v2 = -sum(sample(b) * u[i] for i, b in enumerate(fields2))
                else:
                    v1, v2 = sample(fields1[0]), sample(fields2[0])
                v = interpolate(v1, v2, r, d1, d2, kind)
            if self.n_sub > 1:
                v = v.reshape(-1, self.n_sub).mean(axis=1)
            out[sl.start // self.n_sub: sl.stop // self.n_sub] = v

        starts = range(0, self.n_dir, self.chunk)
        if threads > 1 and len(starts) > 1:
            with ThreadPoolExecutor(threads) as ex:
                list(ex.map(work, starts))
        else:
            for a in starts:
                work(a)
        if self.out_index is not None:
            permuted = np.empty_like(out)
            permuted[self.out_index] = out
            out = permuted
        return out

    def dataset_shape(self):
        return (self.n_slices, self.n_pix) if self.shell_major else (self.n_pix, self.n_slices)

    def chunks(self):
        if self.shell_major:
            return (1, min(self.n_pix, 1 << 20))
        return (self.n_pix, 1)

    def attrs(self):
        return {"origin_pixels": self.origin, "n_sub": self.n_sub}

    def fill(self, ds, idx, lcd, fields1, fields2, d1, d2, kind, threads):
        if self.shell_major:
            for i, d in zip(idx, lcd, strict=True):
                ds[i, :] = self.sample_pair(fields1, fields2, d.value, d1, d2, kind,
                                            threads).astype(np.float32)
            return
        block = np.empty((self.n_pix, len(idx)), np.float32)
        for j, d in enumerate(lcd):
            block[:, j] = self.sample_pair(fields1, fields2, d.value, d1, d2, kind, threads)
        ds[:, idx[0]: idx[-1] + 1] = block


class Ring(Angular):
    """The great circle of postprocess/make_angular_lightcone.py (latitude 0, box centre)."""

    name = "ring"

    def __init__(self, inputs, min_redshift, max_redshift, n_lon=2**15):
        so = inputs.simulation_options
        n = so.HII_DIM
        self.longitude = np.arange(n_lon) * (2 * np.pi / n_lon)
        self.latitude = np.zeros_like(self.longitude)
        lcd = _between_redshifts(inputs, min_redshift, max_redshift, so.cell_size)
        super().__init__(inputs, lcd, self.latitude, self.longitude,
                         origin=np.full(3, n / 2), n_sub=1)

    def attrs(self):
        return super().attrs() | {"n_lon": len(self.longitude)}


class Healpix(Angular):
    """Full-sky HEALPix map per shell, seen from the centre of the box.

    Each pixel is the mean of its 4**oversample HEALPix children (NESTED order at
    nside * 2**oversample), each sampled trilinearly, so pixels larger than the cells
    average the field instead of aliasing it. Stored shell by shell: (n_shells, n_pix),
    in RING (default) or NESTED order.
    """

    name = "healpix"
    shell_major = True

    def __init__(self, inputs, min_redshift, max_redshift, nside=2048, oversample=1,
                 order="ring", shell_spacing=None, chunk=1 << 20):
        from astropy_healpix import HEALPix
        from astropy_healpix.core import nested_to_ring

        so = inputs.simulation_options
        self.nside, self.oversample, self.order = int(nside), int(oversample), order
        nside_sub = self.nside * 2**self.oversample
        hp = HEALPix(nside=nside_sub, order="nested")
        n_dir = int(hp.npix)
        # directions in blocks, so the float64 lon/lat never exist for all of them at once
        unit_dtype = np.float64 if n_dir <= 50_000_000 else np.float32
        unit = np.empty((3, n_dir), dtype=unit_dtype)
        block = 1 << 24
        for a in range(0, n_dir, block):
            lon, lat = hp.healpix_to_lonlat(np.arange(a, min(a + block, n_dir)))
            unit[:, a:a + block] = self._unit_vectors(lat.to_value("rad"), lon.to_value("rad"),
                                                      unit_dtype)
        spacing = so.cell_size if shell_spacing is None else shell_spacing * units.Mpc
        self.shell_spacing = spacing.to_value(units.Mpc)
        lcd = _between_redshifts(inputs, min_redshift, max_redshift, spacing)
        # bypass Angular's own unit-vector construction (already done above)
        Geometry.__init__(self, inputs, lcd)
        self.origin = np.full(3, so.HII_DIM / 2, dtype=np.float64)
        self.n_sub = 4**self.oversample
        self.n_dir = n_dir
        self.n_pix = n_dir // self.n_sub
        self.chunk = max(self.n_sub, (chunk // self.n_sub) * self.n_sub)
        self.unit = unit
        self.out_index = None
        if order == "ring":
            self.out_index = nested_to_ring(np.arange(self.n_pix), self.nside)
        elif order != "nested":
            raise ValueError("order must be 'ring' or 'nested'")

    def attrs(self):
        return super().attrs() | {"nside": self.nside, "oversample": self.oversample,
                                  "order": self.order, "shell_spacing_mpc": self.shell_spacing}


def _trilinear_merged(box1, box2, coords, d, d1, d2) -> np.ndarray:
    """Trilinear sample (periodic) of interpolate(box1, box2, d, d1, d2, "mean_max").

    The same as map_coordinates(order=1, mode="grid-wrap") of the interpolated box, but
    the interpolation is only evaluated at the 8 cells around each point.
    """
    shape = np.array(box1.shape)[:, None]
    fl = np.floor(coords)
    t = coords - fl
    i0 = fl.astype(np.int64) % shape
    i1 = (i0 + 1) % shape
    out = np.zeros(coords.shape[1], dtype=np.float64)
    for cx in (0, 1):
        ix, wx = (i1[0], t[0]) if cx else (i0[0], 1 - t[0])
        for cy in (0, 1):
            iy, wy = (i1[1], t[1]) if cy else (i0[1], 1 - t[1])
            for cz in (0, 1):
                iz, wz = (i1[2], t[2]) if cz else (i0[2], 1 - t[2])
                a, b = box1[ix, iy, iz], box2[ix, iy, iz]
                out += wx * wy * wz * interpolate(a, b, d, d1, d2, "mean_max")
    return out


def _between_redshifts(inputs, zmin, zmax, resolution) -> units.Quantity:
    """Lightconer.between_redshifts: slices every ``resolution`` from d(zmin)."""
    cosmo = inputs.cosmo_params.cosmo
    d0 = cosmo.comoving_distance(zmin).to_value(units.Mpc)
    d1 = cosmo.comoving_distance(zmax).to_value(units.Mpc)
    res = resolution.to_value(units.Mpc)
    return np.arange(d0, d1 + res, res) * units.Mpc


# ── output files ────────────────────────────────────────────────────────────


def output_path(out_dir: Path, geometry: Geometry, quantity: str) -> Path:
    sub = geometry.name if geometry.name != "healpix" else f"healpix_nside{geometry.nside}"
    return Path(out_dir) / sub / f"{quantity}.h5"


def _open_output(path: Path, geometry: Geometry, quantity: str, inputs, nodes, clobber: bool):
    """Create the output file, or open an existing one to resume (same geometry only)."""
    import py21cmfast as p21c

    want = {"format": FORMAT, "quantity": quantity, "geometry": geometry.name,
            "n_slices": geometry.n_slices, **geometry.attrs()}
    if path.exists() and not clobber:
        f = h5py.File(path, "r+")
        for k, v in want.items():
            have = f.attrs.get(k)
            if have is None or not np.array_equal(np.asarray(have), np.asarray(v)):
                f.close()
                raise ValueError(f"{path} was made with {k}={have!r}, not {v!r}; "
                                 "use --clobber to start it again")
        if not np.allclose(f["lightcone_distances"][()], geometry.lc_distances.value):
            f.close()
            raise ValueError(f"{path} has other lightcone distances; use --clobber")
        return f
    path.parent.mkdir(parents=True, exist_ok=True)
    f = h5py.File(path, "w")
    for k, v in want.items():
        f.attrs[k] = v
    f.attrs["py21cmfast_version"] = p21c.__version__
    f.attrs["about"] = (
        "Lightcone of one coeval field, built by postprocess/lightcone/lc_core.py from the "
        "cached coevals. 'lightcone': rect (HII_DIM, HII_DIM, n_slices), ring "
        "(n_lon, n_slices), healpix (n_shells, n_pix). 'interval_done[i]': the slices "
        "between node_redshifts_ascending[i] and [i+1] are written.")
    f.create_dataset("lightcone", shape=geometry.dataset_shape(), dtype=np.float32,
                     chunks=geometry.chunks(), fillvalue=np.nan)
    f["lightcone_distances"] = geometry.lc_distances.value
    f["lightcone_distances"].attrs["unit"] = "Mpc"
    f["lightcone_redshifts"] = geometry.lc_redshifts()
    f["node_redshifts_ascending"] = np.asarray(nodes)
    f["global_mean"] = np.full(len(nodes), np.nan)
    f["interval_done"] = np.zeros(len(nodes) - 1, dtype=bool)
    if isinstance(geometry, Ring):
        f["longitude"] = geometry.longitude
        f["latitude"] = geometry.latitude
    f.flush()
    return f


# ── the pass over the node redshifts ────────────────────────────────────────


def make_lightcones(inputs, paths: CachePaths, quantity: str, geometries, out_dir,
                    threads: int = 1, clobber: bool = False, partial: bool = False) -> list[Path]:
    """Fill the lightcones of one quantity for every geometry, resuming where they stopped.

    With ``partial``, node intervals whose boxes are not cached yet are skipped (left NaN)
    instead of stopping the job, so the lightcones can be filled while the coevals run.
    """
    kinds = field_kinds(inputs)
    fields = source_fields(quantity, geometries)
    unknown = [f for f in fields if f not in kinds]
    if unknown:
        raise KeyError(f"{unknown} are not coeval fields of this run; known: {sorted(kinds)}")
    kind = INTERP_KIND.get(quantity, "mean")
    cell = inputs.simulation_options.cell_size
    cosmo = inputs.cosmo_params.cosmo
    eq = units.pixel_scale(cell / units.pixel)
    nodes = sorted(float(z) for z in inputs.node_redshifts)
    dnode = [cosmo.comoving_distance(z).to(units.pixel, eq).value for z in nodes]

    # slices of each geometry in each node interval (as make_lightcone_slices)
    plan = []  # (interval i, [(geometry, idx, lcd)])
    for i in range(len(nodes) - 1):
        d1, d2 = dnode[i], dnode[i + 1]
        parts = []
        for g in geometries:
            lcpix = g.lc_distances.to(units.pixel, eq)
            idx = np.nonzero((lcpix.value >= d1 * (1 - 1e-6)) & (lcpix.value < d2))[0]
            if len(idx):
                parts.append((g, idx, lcpix[idx]))
        if parts:
            plan.append((i, parts))

    # what is left to do, and are its boxes there? (checked before any file is written)
    done = {}
    for g in geometries:
        p = output_path(out_dir, g, quantity)
        done[g] = np.zeros(len(nodes) - 1, dtype=bool)
        if p.exists() and not clobber:
            try:
                with h5py.File(p, "r") as f:
                    if "interval_done" in f and len(f["interval_done"]) == len(done[g]):
                        done[g] = f["interval_done"][()]
            except OSError as e:
                raise RuntimeError(f"{p} cannot be opened ({e}); a job killed while writing "
                                   "can leave it damaged: rerun with --clobber") from e
    todo = [(i, [p for p in parts if not done[p[0]][i]]) for i, parts in plan]
    todo = [(i, parts) for i, parts in todo if parts]
    cached = {j: all(paths.path(kinds[f], nodes[j]) is not None for f in fields)
              for i, _ in todo for j in (i, i + 1)}
    missing = sorted({nodes[j] for j, ok in cached.items() if not ok})
    if missing and not partial:
        raise FileNotFoundError(f"{fields} not cached yet at {len(missing)} node redshifts, e.g. "
                                f"{missing[:5]}; this script never computes boxes "
                                "(--partial fills what is there)")
    if missing:
        n = len(todo)
        todo = [(i, parts) for i, parts in todo if cached[i] and cached[i + 1]]
        log.info(f"{quantity}: --partial: {n - len(todo)} node intervals skipped, their boxes are "
                 f"not cached yet (z = {missing[0]:.3f} to {missing[-1]:.3f}); rerun later to fill them")

    files = {g: _open_output(output_path(out_dir, g, quantity), g, quantity, inputs, nodes,
                             clobber) for g in geometries}
    try:
        n_slices = sum(len(idx) for _, parts in todo for _, idx, _ in parts)
        log.info(f"{quantity}: {len(todo)} node intervals to do ({n_slices} slices over "
                 f"{', '.join(g.name for g in geometries)}), fields {fields}, {threads} threads")

        # descending redshift, like run_lightcone (a slice on an interval edge is filled by
        # the lower interval last, as in 21cmFAST)
        todo.sort(key=lambda t: -t[0])
        boxes: dict[int, list[np.ndarray]] = {}
        spare: list[list[np.ndarray]] = []
        t_read = t_fill = 0.0
        t0 = time.perf_counter()
        for n_done, (i, parts) in enumerate(todo):
            # boxes above this interval are no longer needed: reuse their memory
            for j in [j for j in boxes if j > i + 1]:
                spare.append(boxes.pop(j))
            for j in (i + 1, i):
                if j in boxes:
                    continue
                t = time.perf_counter()
                buf = spare.pop() if spare else [None] * len(fields)
                boxes[j] = [read_box(paths.path(kinds[f], nodes[j]), kinds[f], f, out=b)
                            for f, b in zip(fields, buf, strict=True)]
                t_read += time.perf_counter() - t
                if quantity != LOS_VELOCITY:
                    mean = float(np.mean(boxes[j][0]))
                    for f in files.values():
                        f["global_mean"][j] = mean
            t = time.perf_counter()
            for g, idx, lcd in parts:
                if np.any(np.diff(idx) != 1):
                    raise RuntimeError("slices of one node interval are not contiguous")
                ds = files[g]["lightcone"]
                g.fill(ds, idx, lcd, boxes[i], boxes[i + 1], dnode[i], dnode[i + 1], kind,
                       threads)
                files[g]["interval_done"][i] = True
                files[g].flush()
            t_fill += time.perf_counter() - t
            log.info(f"{quantity}: z {nodes[i]:.3f}-{nodes[i + 1]:.3f} done "
                     f"({n_done + 1}/{len(todo)}; reading {t_read:.0f} s, slices {t_fill:.0f} s, "
                     f"total {time.perf_counter() - t0:.0f} s)")
        for g, f in files.items():
            done = f["interval_done"][()]
            needed = [i for i, parts in plan if any(p[0] is g for p in parts)]
            f.attrs["complete"] = bool(all(done[i] for i in needed))
    finally:
        for f in files.values():
            f.close()
    return [output_path(out_dir, g, quantity) for g in geometries]
