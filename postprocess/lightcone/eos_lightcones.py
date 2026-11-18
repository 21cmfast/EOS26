"""EOS26 lightcones from the cached coevals, made with tuesday (library of postprocess/lightcone/).

The lightconing itself is tuesday's (``tuesday.simulators.py21cmfast``): one pass over
the node redshifts per quantity, resumable files on disk (``make_lightcones_on_disk``),
21cmFAST's dv/dr correction and RSDs on disk, and a linked 21cmFAST lightcone file per
geometry. This module only fixes the EOS26 geometries and runs them:

* ``rect``     21cmFAST's ``RectilinearLightconer``: line of sight along the box's last
               axis, (HII_DIM, HII_DIM, n_slices).
* ``angular_plane``  the angular plane: ``PLANE_N_LON`` longitudes on latitude 0 of
               the observer frame (the equator of the HEALPix maps), a point each,
               (n_lon, n_slices).
* ``healpix``  full-sky HEALPix maps, Nside ``HEALPIX_NSIDE``, each pixel the mean of its
               4**``HEALPIX_LEVEL`` sub-pixels, (12 Nside^2, n_slices), RING order.
* ``patch``    HEALPix maps of a beam-sized disc: the Nside ``PATCH_NSIDE`` pixels within
               ``PATCH_RADIUS_DEG`` of ``PATCH_CENTER_DEG``, 4**``PATCH_LEVEL`` sub-pixels
               each, (n_patch, n_slices), RING order.

All angular geometries are seen from the centre of the box, in an observer frame rotated
by ``FRAME_ROTATION`` with respect to the box axes (21cmFAST's ``rotation``; none for
EOS26), and use tuesday's ``FastAngularLightconer``. All slices are one cell apart between
``ZMIN`` and ``ZMAX``, as 21cmFAST's ``run_lightcone`` makes them; with RSDs (``RSDS``)
the lightcones are made on the slightly longer distances the RSDs need.

The values of the constants are the choices of the decision list ("EOS26 lightcones:
open decisions", decided 17 Nov 2026). Each run can override them (see
lightcone_quantity.py), but runs of one set of lightcones must use the same values.

The angular samples are made by scipy's ``map_coordinates`` (through cosmotile), on one
core. To use all cores of a job, a HEALPix geometry is split into ``threads`` parts of
consecutive pixels, each filled by its own call to ``make_lightcones_on_disk`` in a
thread, with every box read once and shared between the threads (``SharedFields``).
When all parts of a quantity are complete, they are joined into one file, the same as
a single call on the whole map would write.
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from astropy import units

log = logging.getLogger("21cmFAST")

# ── EOS26 choices (decision list "EOS26 lightcones: open decisions", 17 Nov 2026) ──

#: z = 5-35. With RSDs the lightcones are made on 2-3 more slices at each end (3 cMpc
#: below ZMIN), which must lie within the node redshifts (EOS26: 5.0 to 35.37), so ZMIN
#: is 5.01: the files then start at z = 5.004.
ZMIN, ZMAX = 5.01, 35.0
GEOMETRIES = ("rect", "angular_plane", "healpix", "patch")
#: Geometries whose maps are split into parts filled in parallel threads.
SPLIT = ("healpix", "patch")
#: The released quantities (decision list, 18 Nov), except those made in finalise
#: (brightness_temp_dvdr_with_rsds) and the line intensities ([CII], later).
#: brightness_temp is T_b without the dv/dr correction and RSDs; los_velocity is also
#: what kSZ needs; sfrd_mcg, n_ion and xray_emissivity are the gridded galaxy properties
#: of 21cmFAST's EmissivityFields.
DEFAULT_QUANTITIES = (
    "density",
    "brightness_temp",
    "spin_temperature",
    "neutral_fraction",
    "kinetic_temp_neutral",
    "J_21_LW",
    "sfrd_acg",
    "cumulative_recombinations",
    "los_velocity",
    "ionisation_rate_G12",
    "sfrd_mcg",
    "n_ion",
    "xray_emissivity",
)
#: What the dv/dr correction needs besides brightness_temp.
DVDR_INPUTS = ("tau_21", "los_velocity")
#: Made only for finalise and not released: moved to <out>/intermediate/<dir>/ once the
#: lightcone with RSDs is complete (with RSDS).
NOT_RELEASED = ("tau_21", "brightness_temp_dvdr")

PLANE_N_LON = 2**15  # 0.66 arcmin, 1.5 cMpc at z = 5
HEALPIX_NSIDE = 1024  # 3.4 arcmin pixels
HEALPIX_LEVEL = 2  # 16 sub-pixels, 0.86 arcmin apart
PATCH_NSIDE = 4096  # 0.86 arcmin pixels; each Nside 1024 pixel holds 16 of them
PATCH_LEVEL = 1  # 4 sub-pixels, 0.43 arcmin apart (below a cell at every z)
#: Fixed radius (a cone): ~1.5 HERA FWHM at z = 27, more at lower z.
PATCH_RADIUS_DEG = 45.0
#: (longitude, latitude) of the patch centre in the observer frame, degrees: on
#: latitude 0, so the patch contains part of the angular plane.
PATCH_CENTER_DEG = (0.0, 0.0)
#: The rotation from the observer frame to the box axes: scipy Euler angles in degrees,
#: e.g. ("ZYZ", (a, b, c)), or None. None: the HEALPix maps, the patch and the angular
#: plane share the box axes (the angular plane lies in the box plane z = HII_DIM/2).
FRAME_ROTATION = None
#: Whether to make T_b with dv/dr and RSDs (brightness_temp_dvdr_with_rsds). This sets the
#: distances of all lightcones (RSDs need a few more slices), so it cannot be added later.
RSDS = True
#: Sub-cells per cell for the RSDs (run_lightcone's default).
N_RSD_SUBCELLS = 4


# ── geometries ───────────────────────────────────────────────────────────────


def frame_rotation(spec: str | tuple | None = FRAME_ROTATION):
    """The rotation of the observer frame: a ``(seq, angles_deg)`` pair, "none" or None.

    A string "ZYZ:30,40,50" is read as ``("ZYZ", (30, 40, 50))``.
    """
    from scipy.spatial.transform import Rotation

    if spec is None or (isinstance(spec, str) and spec.lower() == "none"):
        return None
    if isinstance(spec, str):
        seq, _, angles = spec.partition(":")
        spec = (seq, tuple(float(a) for a in angles.split(",")))
    seq, angles = spec
    return Rotation.from_euler(seq, angles, degrees=True)


def dir_name(geometry: str, opts: Mapping) -> str:
    """The directory of a geometry's files in the output directory."""
    if geometry == "healpix":
        return f"healpix_nside{opts['healpix_nside']}"
    if geometry == "patch":
        return f"patch_nside{opts['patch_nside']}"
    return geometry


def default_options(**over) -> dict:
    """The geometry options (constants above), with some replaced."""
    opts = {
        "zmin": ZMIN,
        "zmax": ZMAX,
        "plane_n_lon": PLANE_N_LON,
        "healpix_nside": HEALPIX_NSIDE,
        "healpix_level": HEALPIX_LEVEL,
        "patch_nside": PATCH_NSIDE,
        "patch_level": PATCH_LEVEL,
        "patch_radius_deg": PATCH_RADIUS_DEG,
        "patch_center_deg": PATCH_CENTER_DEG,
        "rotation": FRAME_ROTATION,
        "rsds": RSDS,
    }
    unknown = set(over) - set(opts)
    if unknown:
        raise TypeError(f"unknown options {sorted(unknown)}")
    opts.update({k: v for k, v in over.items() if v is not None})
    return opts


def patch_pixels(opts: Mapping) -> np.ndarray:
    """RING indices of the patch's pixels: those whose centres are within the radius.

    The same pixels as tuesday's ``disc_pixels``, which takes more than 10 minutes at
    Nside 4096 for a 10 deg disc (astropy-healpix's cone search). In RING order the
    latitude of the pixel centres never increases with the index, so the rings that can
    hold such pixels are one range of indices, found by bisection; the angular distance
    of their centres is then computed in blocks.
    """
    from astropy.coordinates import angular_separation
    from astropy_healpix import HEALPix

    nside = opts["patch_nside"]
    lon0, lat0 = (np.deg2rad(a) for a in opts["patch_center_deg"])
    radius = np.deg2rad(opts["patch_radius_deg"])
    grid = HEALPix(nside=nside, order="ring")
    npix = int(grid.npix)

    def lat(i):
        return float(grid.healpix_to_lonlat(np.array([i]))[1].to_value("rad")[0])

    def first(pred):  # the first index whose pixel centre satisfies pred (monotonic)
        lo, hi = 0, npix
        while lo < hi:
            mid = (lo + hi) // 2
            if pred(lat(mid)):
                hi = mid
            else:
                lo = mid + 1
        return lo

    top, bottom = lat0 + radius, lat0 - radius
    start, stop = first(lambda x: x <= top + 1e-12), first(lambda x: x < bottom - 1e-12)
    keep = []
    for a in range(start, stop, 1 << 22):
        idx = np.arange(a, min(a + (1 << 22), stop))
        lon, la = grid.healpix_to_lonlat(idx)
        sep = angular_separation(lon.to_value("rad"), la.to_value("rad"), lon0, lat0)
        keep.append(idx[sep <= radius])
    return np.concatenate(keep) if keep else np.zeros(0, dtype=int)


def part_ranges(n: int, parts: int) -> list[slice]:
    """``parts`` slices of consecutive indices covering ``range(n)``, as equal as possible."""
    edges = np.linspace(0, n, max(1, min(parts, n)) + 1).round().astype(int)
    return [slice(a, b) for a, b in zip(edges[:-1], edges[1:], strict=True)]


class _Run:
    """What every lightconer of one run shares: distances, origin, rotation, CLASS."""

    def __init__(self, inputs, opts: Mapping):
        import py21cmfast as p21c

        self.inputs, self.opts = inputs, dict(opts)
        so = inputs.simulation_options
        self.cosmo = inputs.cosmo_params.cosmo
        self.cell = so.cell_size
        self.origin = np.full(3, so.HII_DIM / 2) * units.pixel
        self.rotation = frame_rotation(opts["rotation"])
        # 21cmFAST's slices between the two redshifts, one cell apart
        self.requested = p21c.RectilinearLightconer.between_redshifts(
            min_redshift=opts["zmin"], max_redshift=opts["zmax"],
            resolution=self.cell, cosmo=self.cosmo,
        ).lc_distances
        self._classy = None

    def classy(self):
        """CLASS for the run's cosmology, run once (for the distances the RSDs need)."""
        if self._classy is None:
            from py21cmfast.wrapper.classy_interface import run_classy

            cp = self.inputs.cosmo_params
            self._classy = run_classy(
                h=cp.hlittle, Omega_cdm=cp.OMm - cp.OMb, Omega_b=cp.OMb,
                n_s=cp.POWER_INDEX, sigma8=cp.SIGMA_8, output="vTk",
            )
        return self._classy

    def finish(self, lightconer):
        """With RSDs, extend the lightconer to the distances they need (tuesday)."""
        if not self.opts["rsds"]:
            return lightconer
        from tuesday.simulators.py21cmfast.lightcones import rsd_lightconer

        return rsd_lightconer(lightconer, self.inputs, classy_output=self.classy())

    def angular_kw(self) -> dict:
        return {
            "min_redshift": self.opts["zmin"], "max_redshift": self.opts["zmax"],
            "resolution": self.cell, "cosmo": self.cosmo, "origin": self.origin,
            "rotation": self.rotation, "quantities": ("density",),
        }


def lightconers(inputs, geometry: str, opts: Mapping, *, parts: int = 1, run: _Run | None = None):
    """The lightconers of one geometry, by name (their directory in the output directory).

    With ``parts`` > 1, a HEALPix geometry (``SPLIT``) comes as that many lightconers of
    consecutive pixels, named ``parts/<dir>/<k>-of-<parts>``.
    """
    import py21cmfast as p21c
    from tuesday.simulators.py21cmfast.lightconers import FastAngularLightconer

    run = run or _Run(inputs, opts)
    name = dir_name(geometry, opts)
    if geometry == "rect":
        lc = p21c.RectilinearLightconer.between_redshifts(
            min_redshift=opts["zmin"], max_redshift=opts["zmax"],
            resolution=run.cell, cosmo=run.cosmo, quantities=("density",),
        )
        return {name: run.finish(lc)}
    if geometry == "angular_plane":
        n = opts["plane_n_lon"]
        lon = np.arange(n) * (2 * np.pi / n)
        lc = FastAngularLightconer.between_redshifts(
            latitude=np.zeros(n), longitude=lon, **run.angular_kw()
        )
        return {name: run.finish(lc)}
    if geometry == "healpix":
        nside, level = opts["healpix_nside"], opts["healpix_level"]
        pixels = np.arange(12 * nside**2)
    elif geometry == "patch":
        nside, level = opts["patch_nside"], opts["patch_level"]
        pixels = patch_pixels(opts)
    else:
        raise ValueError(f"unknown geometry {geometry!r}; one of {GEOMETRIES}")

    def make(pix):
        full_sky = geometry == "healpix" and pix.size == 12 * nside**2
        lc = FastAngularLightconer.healpix(
            nside, order="ring", subsample_level=level,
            pixels=None if full_sky else pix, **run.angular_kw(),
        )
        return run.finish(lc)

    if parts <= 1:
        return {name: make(pixels)}
    ranges = part_ranges(pixels.size, parts)
    k = len(ranges)
    return {f"parts/{name}/{i + 1:02d}-of-{k:02d}": make(pixels[r]) for i, r in enumerate(ranges)}


# ── boxes shared by threads ──────────────────────────────────────────────────


class SharedFields:
    """tuesday's ``CachedFields`` shared by threads: each box is read once, threads in step.

    Every thread of a pass goes through the node redshifts in the same order (high to low
    redshift), reading the box at the far end of each interval. A box is read by the
    first thread that asks for it and kept until no thread needs it any more. A thread
    may read a node redshift at most one past the slowest other thread, so at most three
    node redshifts are held at once (at 1500^3: 40 GB for one field, 122 GB for the three
    velocities), and no box is read twice. All threads first wait until each has asked
    for its first box (or finished), so that none starts ahead. Each thread must call
    ``done()`` when it finishes. The boxes are read-only.
    """

    def __init__(self, fields, n_threads: int = 1):
        self._fields = fields
        self.inputs = fields.inputs
        self.kinds = fields.kinds
        self.node_redshifts = fields.node_redshifts
        self._index = {z: i for i, z in enumerate(self.node_redshifts)}
        self._cond = threading.Condition()
        self._waiting = n_threads  # threads that have not asked for a box nor finished
        self._pos: dict[int, int] = {}  # thread -> node index it reads or has read last
        self._boxes: dict[tuple[int, str], np.ndarray] = {}
        self._loading: set[tuple[int, str]] = set()
        self.reads = 0

    def has(self, redshift: float, fields: Iterable[str]) -> bool:
        return self._fields.has(redshift, fields)

    def path(self, redshift: float, field: str) -> Path:
        return self._fields.path(redshift, field)

    def _evict(self) -> None:
        # no thread asks for a node redshift below the slowest one's previous node again
        if self._pos:
            low = min(self._pos.values()) - 1
            for key in [k for k in self._boxes if k[0] < low]:
                del self._boxes[key]

    def done(self) -> None:
        """Call when a thread has finished (it no longer holds back the others)."""
        with self._cond:
            tid = threading.get_ident()
            if self._pos.pop(tid, None) is None:
                self._waiting -= 1
            self._evict()
            self._cond.notify_all()

    def read(self, redshift: float, field: str) -> np.ndarray:
        node = self._index[redshift]
        key = (node, field)
        tid = threading.get_ident()
        with self._cond:
            first = tid not in self._pos
            self._pos[tid] = max(node, self._pos.get(tid, node))
            if first:
                self._waiting -= 1
                self._cond.notify_all()
                self._cond.wait_for(lambda: self._waiting <= 0)

            def may_go():
                others = [p for t, p in self._pos.items() if t != tid]
                return not others or node <= min(others) + 1

            self._cond.wait_for(may_go)
            while key in self._loading:
                self._cond.wait()
            if key in self._boxes:
                return self._boxes[key]
            self._loading.add(key)
        try:
            box = np.asarray(self._fields.read(redshift, field))
            box.flags.writeable = False
        finally:
            with self._cond:
                self._loading.discard(key)
                self._cond.notify_all()
        with self._cond:
            self.reads += 1
            self._boxes[key] = box
            self._evict()
            self._cond.notify_all()
        return box


# ── one quantity, all geometries ─────────────────────────────────────────────


def _complete(path: Path) -> bool:
    """Whether a file is a complete lightcone store."""
    from tuesday.core.lightcones.store import LightconeStore

    path = Path(path)
    if not path.exists():
        return False
    try:
        with LightconeStore.open(path) as store:
            return bool(store.complete)
    except (OSError, ValueError, KeyError):
        return False


def join_parts(out_dir: Path, name: str, full, part_names: Sequence[str], quantity: str,
               inputs, *, keep_parts: bool = False, clobber: bool = False) -> Path | None:
    """Join the complete part files of one quantity into ``out_dir/<name>/<quantity>.h5``.

    The parts hold consecutive pixels, so the joined file is what one call of
    ``make_lightcones_on_disk`` with ``full`` writes. Returns None (nothing written) if a
    part is not complete. The part files of the quantity are deleted afterwards unless
    ``keep_parts``.
    """
    from tuesday.core.lightcones.store import LightconeStore
    from tuesday.simulators.py21cmfast.lightcones import lightconer_metadata

    out_dir = Path(out_dir)
    dst = out_dir / name / f"{quantity}.h5"
    srcs = [out_dir / p / f"{quantity}.h5" for p in part_names]
    if _complete(dst) and not clobber:
        return dst
    if not all(_complete(s) for s in srcs):
        return None
    tmp = dst.with_name(f".{dst.name}.tmp")
    dst.parent.mkdir(parents=True, exist_ok=True)
    stores = [LightconeStore.open(s) for s in srcs]
    try:
        first = stores[0]
        with LightconeStore.open_or_create(
            tmp, quantity=quantity, shape=full.get_shape(inputs.simulation_options),
            distances=first.distances, redshifts=first.redshifts,
            node_redshifts=first.node_redshifts, metadata=lightconer_metadata(full),
            clobber=True,
        ) as joined:
            if sum(s.shape[0] for s in stores) != joined.shape[0]:
                raise ValueError(f"the parts of {name}/{quantity} do not make the whole map")
            row = 0
            for s in stores:
                if not np.allclose(s.distances, first.distances, rtol=1e-10):
                    raise ValueError(f"{s.path} has other distances than {first.path}")
                step = max(1, (2**28 // max(1, int(np.prod(s.shape[1:])))))
                for a in range(0, s.shape[0], step):
                    block = s.lightcone[a:a + step]
                    joined.lightcone[row + a:row + a + block.shape[0]] = block
                row += s.shape[0]
            for node, mean in enumerate(first.global_mean):
                if np.isfinite(mean):
                    joined.set_global_mean(node, float(mean))
            joined.mark_done(range(joined.done.size))
    finally:
        for s in stores:
            s.close()
    tmp.replace(dst)
    if not keep_parts:
        for s in srcs:
            s.unlink()
    return dst


def make_quantity(inputs, cache_dir: str | Path, quantity: str, geometries: Sequence[str],
                  out_dir: str | Path, opts: Mapping, *, threads: int = 1,
                  partial: bool = False, clobber: bool = False,
                  keep_parts: bool = False) -> dict[str, Path | None]:
    """Fill the lightcones of one quantity for the given geometries; resumable.

    rect and the angular plane are filled by one thread; each HEALPix geometry (``SPLIT``) is split
    into ``threads`` parts filled in parallel, then joined when complete. Every box is
    read once (``SharedFields``). Returns the file of each geometry (None for a HEALPix
    geometry whose parts are not complete yet, e.g. with ``partial``).
    """
    import py21cmfast as p21c
    from py21cmfast.io.caching import RunCache
    from tuesday.simulators.py21cmfast.lightcones import CachedFields, make_lightcones_on_disk

    out_dir = Path(out_dir)
    run = _Run(inputs, opts)
    cache = RunCache.from_inputs(inputs, cache=p21c.OutputCache(str(cache_dir)))
    groups: list[dict] = []
    single: dict = {}
    split: dict[str, tuple] = {}  # dir -> (full lightconer, part names)
    result: dict[str, Path | None] = {}
    for g in geometries:
        name = dir_name(g, opts)
        dst = out_dir / name / f"{quantity}.h5"
        kept = out_dir / "intermediate" / name / f"{quantity}.h5"
        if quantity in NOT_RELEASED and _complete(kept) and not clobber:
            log.info(f"{quantity}: {kept} is complete (set aside by finalise)")
            result[g] = kept
            continue
        if g in SPLIT and threads > 1:
            if _complete(dst) and not clobber:
                log.info(f"{quantity}: {dst} is complete")
                result[g] = dst
                continue
            parts = lightconers(inputs, g, opts, parts=threads, run=run)
            groups += [{n: lc} for n, lc in parts.items()]
            split[g] = (name, parts)
        else:
            single.update(lightconers(inputs, g, opts, run=run))
            result[g] = dst
    if single:
        groups.insert(0, single)
    source = SharedFields(CachedFields(cache), n_threads=len(groups))
    log.info(f"{quantity}: {len(groups)} thread(s) for {list(geometries)} "
             f"({', '.join(f'{len(v[1])} parts of {k}' for k, v in split.items()) or 'no parts'})")

    t0 = time.perf_counter()
    def fill(group):
        try:
            return make_lightcones_on_disk(group, [quantity], source, out_dir,
                                           partial=partial, clobber=clobber)
        finally:
            source.done()

    if groups:
        with ThreadPoolExecutor(len(groups)) as ex:
            futures = [ex.submit(fill, grp) for grp in groups]
            for f in futures:
                f.result()
    log.info(f"{quantity}: filled in {time.perf_counter() - t0:.0f} s, "
             f"{source.reads} boxes read")

    for g, (name, parts) in split.items():
        full = lightconers(inputs, g, opts, parts=1, run=run)[name]
        result[g] = join_parts(out_dir, name, full, list(parts), quantity, inputs,
                               keep_parts=keep_parts, clobber=clobber)
        if result[g] is None:
            log.info(f"{quantity}: {name} not joined yet (parts not complete; rerun later)")
        else:
            log.info(f"{quantity}: joined {len(parts)} parts -> {result[g]}")
            parts_dir = out_dir / "parts" / name
            if not keep_parts and parts_dir.is_dir() and not any(parts_dir.rglob("*.h5")):
                shutil.rmtree(parts_dir)
    top = out_dir / "parts"
    if not keep_parts and top.is_dir() and not any(top.iterdir()):
        top.rmdir()
    return result


# ── after all quantities: dv/dr, RSDs, linked files ──────────────────────────


def degrade_dir(src_dir: Path, dst_dir: Path, nside: int, *, clobber: bool = False) -> list[Path]:
    """Full-sky HEALPix lightcones of ``src_dir`` averaged to ``nside`` (tuesday's degrade).

    Each pixel is the mean of the pixels that tile it, slice block by slice block. For
    the coeval fields this is the map at ``nside`` with more sub-pixels; for
    brightness_temp_dvdr it is the mean of the corrected pixels. Not made for EOS26
    (decision list: users average the Nside 1024 maps themselves); ``finalise`` makes
    it with ``degrade_nside``.
    """
    from tuesday.core.lightcones import degrade
    from tuesday.core.lightcones.store import LightconeStore

    done = []
    for src in sorted(Path(src_dir).glob("*.h5")):
        if not _complete(src):
            continue
        dst = Path(dst_dir) / src.name
        if _complete(dst) and not clobber:
            done.append(dst)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(f".{dst.name}.tmp")
        with LightconeStore.open(src) as s:
            nside_in = round(float(np.sqrt(s.shape[0] / 12)))
            meta = {k: v for k, v in s.metadata.items() if k not in ("latitude", "longitude")}
            ratio = nside_in // nside
            meta |= {"degraded_from_nside": nside_in, "nside": nside,
                     "n_subsamples": int(meta.get("n_subsamples", 1)) * ratio**2}
            with LightconeStore.open_or_create(
                tmp, quantity=s.quantity, shape=(12 * nside**2, s.shape[1]),
                distances=s.distances, redshifts=s.redshifts,
                node_redshifts=s.node_redshifts, metadata=meta, clobber=True,
            ) as d:
                step = s.lightcone.chunks[-1]
                for a in range(0, s.shape[1], step):
                    d.lightcone[:, a:a + step] = degrade(s.lightcone[:, a:a + step], nside,
                                                         order="ring")
                for node, mean in enumerate(s.global_mean):
                    if np.isfinite(mean):
                        d.set_global_mean(node, float(mean))
                d.mark_done(range(d.done.size))
        tmp.replace(dst)
        done.append(dst)
    return done


def _restore(out_dir: Path, d: Path) -> None:
    """Move the not-released files of geometry ``d`` back from ``intermediate`` (rerun)."""
    kept = out_dir / "intermediate" / d.name
    for q in NOT_RELEASED:
        src, dst = kept / f"{q}.h5", d / f"{q}.h5"
        if src.exists() and not dst.exists():
            src.replace(dst)


def _set_aside(out_dir: Path, d: Path, link: Path) -> None:
    """Move the not-released files of ``d`` to ``intermediate`` and unlink them in ``link``."""
    import h5py

    with h5py.File(link, "a") as f:
        lightcones = f["lightcones"]
        for name in list(lightcones):
            target = lightcones.get(name, getlink=True)
            if isinstance(target, h5py.ExternalLink) and Path(target.filename).stem in NOT_RELEASED:
                del lightcones[name]
    kept = out_dir / "intermediate" / d.name
    for q in NOT_RELEASED:
        src = d / f"{q}.h5"
        if src.exists():
            kept.mkdir(parents=True, exist_ok=True)
            src.replace(kept / src.name)


def finalise(out_dir: str | Path, inputs, opts: Mapping, *, max_memory: float = 8e9,
             degrade_nside: int | None = None, clobber: bool = False) -> dict[str, Path]:
    """dv/dr, RSDs and a linked lightcone file per geometry; the intermediate files aside.

    For every geometry directory in ``out_dir`` (not ``parts`` or ``intermediate``):
    brightness_temp_dvdr (when brightness_temp, los_velocity and tau_21 are complete
    there); with RSDs, brightness_temp_dvdr_with_rsds; with ``degrade_nside``, the
    full-sky maps averaged to that Nside (not for EOS26); and ``<dir>.h5``, a 21cmFAST
    lightcone file linking to the complete files (``LightCone.from_file`` reads it; it
    needs the files next to it). In it, as in run_lightcone's output,
    ``brightness_temp_with_rsds`` is T_b with dv/dr and RSDs and
    ``brightness_temp_no_dvdr`` is T_b without either.

    With RSDs, once brightness_temp_dvdr_with_rsds is complete, the files that are not
    released (``NOT_RELEASED``: tau_21 and the T_b with dv/dr only) are moved to
    ``out_dir/intermediate/<dir>/`` and left out of ``<dir>.h5``. A rerun moves them back
    when it needs them (e.g. with ``clobber``). Delete ``intermediate`` to save space.
    """
    from tuesday.simulators.py21cmfast.lightcones import (
        DVDR, WITH_RSDS, apply_rsds_on_disk, include_dvdr_on_disk, link_lightcone_file,
    )

    out_dir = Path(out_dir)
    run = _Run(inputs, opts)
    full_sky = dir_name("healpix", opts)
    degraded = f"healpix_nside{degrade_nside}" if degrade_nside else None
    dirs = sorted(d for d in out_dir.iterdir()
                  if d.is_dir() and d.name not in ("parts", "intermediate", degraded)
                  and not d.name.startswith("."))
    links = {}
    for d in dirs:
        t = time.perf_counter()
        rsd_file = d / f"{DVDR}{WITH_RSDS}.h5"
        rsds_done = bool(opts["rsds"]) and _complete(rsd_file) and not clobber
        if not rsds_done:
            _restore(out_dir, d)
            need = ["brightness_temp", "los_velocity"]
            if inputs.astro_options.USE_TS_FLUCT:
                need.append("tau_21")
            if all(_complete(d / f"{q}.h5") for q in need):
                include_dvdr_on_disk(d, inputs, max_memory=max_memory, clobber=clobber)
                if opts["rsds"]:
                    apply_rsds_on_disk(d, inputs, [DVDR], n_rsd_subcells=N_RSD_SUBCELLS,
                                       max_memory=max_memory, clobber=clobber)
            else:
                log.info(f"{d.name}: no dv/dr yet; missing or incomplete: "
                         f"{[q for q in need if not _complete(d / f'{q}.h5')]}")
        lc_distances = run.requested if opts["rsds"] else None
        if d.name == full_sky and degraded:
            if degrade_dir(d, out_dir / degraded, degrade_nside, clobber=clobber):
                links[degraded] = link_lightcone_file(out_dir / degraded, inputs,
                                                      lc_distances=lc_distances)
        if any(_complete(p) for p in d.glob("*.h5")):
            links[d.name] = link_lightcone_file(d, inputs, lc_distances=lc_distances)
            if opts["rsds"] and _complete(rsd_file):
                _set_aside(out_dir, d, links[d.name])
        log.info(f"{d.name}: finalised in {time.perf_counter() - t:.0f} s")
    return links


def default_out_dir(cache_dir: str | Path) -> Path:
    """Where the lightcones go: $EOS26_LIGHTCONE_DIR/<cache name>, else scratch on Gadi.

    On Gadi: /scratch/qp00/$USER/lightcones/<cache directory name> (gdata is full; NCI
    removes scratch files that have not been accessed for a long time, so copy the
    finished products to gdata or massdata). Elsewhere: <cache>/lightcones.
    """
    import getpass

    name = Path(str(cache_dir).rstrip("/")).name
    if os.environ.get("EOS26_LIGHTCONE_DIR"):
        return Path(os.environ["EOS26_LIGHTCONE_DIR"]).expanduser() / name
    scratch = Path("/scratch/qp00")
    if scratch.is_dir():
        return scratch / getpass.getuser() / "lightcones" / name
    return Path(cache_dir) / "lightcones"
