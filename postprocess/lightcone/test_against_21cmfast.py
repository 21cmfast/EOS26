"""Check postprocess/lightcone/ (tuesday on disk) against 21cmFAST's run_lightcone on a small run.

    python postprocess/lightcone/test_against_21cmfast.py --cache /tmp/lc_test   # ~10 min, 2 cores

Runs (or reuses, from --cache) a 32^3 'minihalos-discrete' + 'size-tiny' simulation
(KEEP_3D_VELOCITIES=True, as EOS26). Makes the EOS geometries of eos_lightcones.py at
small sizes (angular plane of 64 longitudes; full sky at Nside 4 with 4 sub-pixels; a
40 deg patch at Nside 8 with 4 sub-pixels; a generic frame rotation and patch centre, so
that the rotation is exercised, where EOS26 uses none and (0, 0)) twice:

* with eos_lightcones.make_quantity + finalise (one pass per quantity on disk, the
  HEALPix geometries split into parts filled in threads and joined, dv/dr, Nside 2
  maps averaged from Nside 4, linked lightcone files);
* with p21c.run_lightcone and the same lightconers (the reference, with its default
  dv/dr correction).

and compares every lightcone and global mean. Also: the joined parts against a single
unsplit pass; the Nside 2 maps against run_lightcone at Nside 2 with 16 sub-pixels
(linear fields); the angular plane of tuesday's FastAngularLightconer against 21cmFAST's
own AngularLightconer; and, unless --no-rsds, the RSD lightcones (rect, angular plane)
against run_lightcone(apply_rsds=True), with the not-released files set aside.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(1, str(Path(__file__).resolve().parent))

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--cache", required=True, help="cache directory (reused if it has the boxes)")
parser.add_argument("--out", default=None, help="output directory (default <cache>/lightcone_test)")
parser.add_argument("--threads", type=int, default=3, help="parts of each HEALPix geometry (default 3)")
parser.add_argument("--no-rsds", action="store_true", help="skip the RSD check")
args = parser.parse_args()

warnings.simplefilter("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("21cmFAST")

import h5py  # noqa: E402
import py21cmfast as p21c  # noqa: E402

import eos_lightcones as el  # noqa: E402

QUANTITIES = ["density", "brightness_temp", "spin_temperature", "neutral_fraction", "z_reion",
              "J_21_LW", "sfrd_acg", "kinetic_temp_neutral", "cumulative_recombinations",
              "ionisation_rate_G12", "sfrd_mcg", "n_ion", "xray_emissivity"]
ALL = [*QUANTITIES, *el.DVDR_INPUTS]

inputs = p21c.InputParameters.from_template(
    ["minihalos-discrete", "size-tiny"], random_seed=1, HII_DIM=32, BOX_LEN=48.0,
    ZPRIME_STEP_FACTOR=1.03, Z_HEAT_MAX=35.0, N_THREADS=1,
    KEEP_3D_VELOCITIES=True)  # as EOS26; needed by angular lightcones with dv/dr
cache = p21c.OutputCache(args.cache)
out = Path(args.out) if args.out else Path(args.cache) / "lightcone_test"
write = p21c.CacheConfig(radiation_fields=False)
if not all(Path(p).exists() for p in p21c.io.caching.RunCache.from_inputs(inputs, cache=cache).BrightnessTemp.values()):
    log.info("making the coevals")
    p21c.run_lightcone(lightconer=p21c.RectilinearLightconer.between_redshifts(
        min_redshift=6.0, max_redshift=34.0, resolution=inputs.simulation_options.cell_size,
        cosmo=inputs.cosmo_params.cosmo, quantities=["density"]),
        inputs=inputs, cache=cache, write=p21c.CacheConfig(), progressbar=False)

# test values: a generic rotation, so that the rotation is exercised; a patch centre off
# the angular plane; no RSDs (RSDs separately below)
opts = el.default_options(zmin=6.0, zmax=34.0, plane_n_lon=64, healpix_nside=4, healpix_level=1,
                          patch_nside=8, patch_level=1, patch_radius_deg=40.0,
                          rotation="ZYZ:77,18,0", patch_center_deg=(0.0, -30.7), rsds=False)
geometries = list(el.GEOMETRIES)
failures: list[tuple[str, str]] = []


def check(label, mine, theirs, exact=False):
    mine, theirs = np.asarray(mine, dtype=np.float64), np.asarray(theirs, dtype=np.float64)
    same_shape = mine.shape == theirs.shape
    diff = np.abs(mine - theirs) if same_shape else np.array([np.inf])
    scale = np.nanmax(np.abs(theirs)) or 1.0
    rel = float(np.nanmax(diff) / scale)
    n_diff = int(np.count_nonzero(diff)) if same_shape else -1
    ok = same_shape and (rel == 0 if exact else rel < 1e-6) and np.array_equal(np.isnan(mine), np.isnan(theirs))
    print(f"{label:46s} shape {mine.shape} max|diff|/max|ref| = {rel:.2e} ({n_diff} differ) {'ok' if ok else 'FAIL'}")
    if not ok:
        failures.append((label, ""))


def reference(lightconer, **kw):
    t = time.time()
    lc = p21c.run_lightcone(lightconer=attrs_evolve(lightconer, quantities=tuple(QUANTITIES)),
                            inputs=inputs, cache=cache, regenerate=False, write=write,
                            progressbar=False, **kw)
    log.info(f"reference {type(lightconer).__name__}: {time.time() - t:.1f} s")
    return lc


def attrs_evolve(obj, **kw):
    import attrs
    return attrs.evolve(obj, **kw)


# the EOS26 choices (decision list, 17 Nov)
d = el.default_options()
ok = (d["rotation"] is None and d["patch_center_deg"] == (0.0, 0.0) and d["patch_radius_deg"] == 45.0
      and d["rsds"] is True and d["zmin"] == 5.01 and d["zmax"] == 35.0 and d["plane_n_lon"] == 2**15
      and (d["healpix_nside"], d["healpix_level"], d["patch_nside"], d["patch_level"]) == (1024, 2, 4096, 1))
print(f"default options are the decided ones: {'ok' if ok else 'FAIL'}")
if not ok:
    failures.append(("defaults", str(d)))

# the patch's pixels against tuesday's disc_pixels (eos_lightcones selects them faster)
from astropy import units as u  # noqa: E402
from tuesday.core.lightcones import disc_pixels  # noqa: E402

for nside, centre, radius in ((32, (0.0, -30.7), 10.0), (64, (123.4, 56.7), 25.0), (128, (300.0, -85.0), 7.5)):
    o = el.default_options(patch_nside=nside, patch_center_deg=centre, patch_radius_deg=radius)
    same = np.array_equal(el.patch_pixels(o), disc_pixels(nside, centre[0] * u.deg, centre[1] * u.deg,
                                                          radius * u.deg, order="ring"))
    print(f"patch pixels = tuesday disc_pixels (Nside {nside}, {radius} deg): {'ok' if same else 'FAIL'}")
    if not same:
        failures.append(("patch pixels", str(nside)))


class Reads(logging.Handler):
    """The number of boxes each make_quantity call read, from its log line."""

    def __init__(self):
        super().__init__()
        self.counts = []

    def emit(self, record):
        msg = record.getMessage()
        if "boxes read" in msg:
            self.counts.append(int(msg.split(",")[-1].split()[0]))


reads = Reads()
log.addHandler(reads)

# ── on disk, as the EOS jobs do it ───────────────────────────────────────────
shutil.rmtree(out, ignore_errors=True)
t = time.time()
for q in ALL:
    el.make_quantity(inputs, args.cache, q, geometries, out, opts, threads=args.threads, clobber=True)
links = el.finalise(out, inputs, opts, degrade_nside=2, clobber=True)
# every box read once: the node redshifts around z = 6-34, once per field
n_nodes = 56
expected = [3 * n_nodes if q == "los_velocity" else n_nodes for q in ALL]
ok = reads.counts == expected
print(f"boxes read per quantity {reads.counts} (expected {expected}): {'ok' if ok else 'FAIL'}")
if not ok:
    failures.append(("boxes read", str(reads.counts)))
log.info(f"eos_lightcones: {time.time() - t:.1f} s; linked files {sorted(links)}")
assert not (out / "parts").exists(), "the part files should be gone after joining"

# resume: nothing left to do
t = time.time()
el.make_quantity(inputs, args.cache, "density", geometries, out, opts, threads=args.threads)
log.info(f"resume: {time.time() - t:.1f} s")

# ── against run_lightcone with the same lightconers ──────────────────────────
for g in geometries:
    name = el.dir_name(g, opts)
    lcn = el.lightconers(inputs, g, opts)[name]
    ref = reference(lcn)
    with h5py.File(links[name], "r") as f:
        for q in ALL:
            mine = f["lightcones"][q][()]
            check(f"{name} {q}", mine, ref.lightcones[q], exact=(g == "rect"))
        # the files record the mean of each box they read: NaN at the node redshifts
        # outside the lightcone, which run_lightcone also averages
        node_z = np.asarray(inputs.node_redshifts, dtype=float)
        dist = np.asarray([inputs.cosmo_params.cosmo.comoving_distance(z).value for z in node_z])
        d = np.asarray(f["lightcone_distances"][()])
        below = np.max(np.where(dist <= d.min(), dist, -np.inf))
        above = np.min(np.where(dist >= d.max(), dist, np.inf))
        read = (dist >= below) & (dist <= above)
        for q, v in ref.global_quantities.items():
            if q in f["global_quantities"]:
                g_mine = f["global_quantities"][q][()]
                ok_nan = np.array_equal(np.isfinite(g_mine), read)
                check(f"{name} global {q} ({int(read.sum())} of {read.size} nodes)",
                      g_mine[read], np.asarray(v)[read])
                if not ok_nan:
                    failures.append((f"{name} global {q}", "NaN pattern"))
    if g in ("rect", "angular_plane"):
        p21c.LightCone.from_file(links[name])  # opens as a 21cmFAST lightcone

# Nside 2 from Nside 4 (linear fields) against a direct Nside 2 map with 16 sub-pixels
from tuesday.simulators.py21cmfast.lightconers import FastAngularLightconer  # noqa: E402

run = el._Run(inputs, opts)
direct = FastAngularLightconer.healpix(2, order="ring", subsample_level=2, **run.angular_kw())
ref2 = reference(direct)
from tuesday.core.lightcones import degrade  # noqa: E402

with h5py.File(links["healpix_nside2"], "r") as f, h5py.File(links["healpix_nside4"], "r") as f4:
    for q in ("density", "neutral_fraction", "z_reion", "tau_21"):
        check(f"healpix_nside2 (averaged) {q}", f["lightcones"][q][()], ref2.lightcones[q])
    # the dv/dr-corrected map is the mean of the corrected Nside 4 pixels
    check("healpix_nside2 brightness_temp = degrade(nside 4)", f["lightcones"]["brightness_temp"][()],
          degrade(f4["lightcones"]["brightness_temp"][()], 2, order="ring"), exact=True)

# joined parts against one unsplit pass
single = out.parent / (out.name + "_single")
shutil.rmtree(single, ignore_errors=True)
el.make_quantity(inputs, args.cache, "density", ["healpix", "patch"], single, opts, threads=1)
for g in ("healpix", "patch"):
    name = el.dir_name(g, opts)
    with h5py.File(out / name / "density.h5") as a, h5py.File(single / name / "density.h5") as b:
        check(f"{name} joined parts vs one pass", a["lightcone"][()], b["lightcone"][()], exact=True)

# tuesday's angular plane against 21cmFAST's own AngularLightconer (same directions and frame)
plane = el.lightconers(inputs, "angular_plane", opts)["angular_plane"]
stock = p21c.AngularLightconer(latitude=plane.latitude, longitude=plane.longitude, origin=plane.origin,
                               rotation=plane.rotation, lc_distances=plane.lc_distances,
                               cosmo=plane.cosmo, quantities=tuple(QUANTITIES))
ref_stock = reference(stock)
with h5py.File(links["angular_plane"], "r") as f:
    for q in ("density", "brightness_temp", "los_velocity", "z_reion"):
        check(f"angular plane vs stock AngularLightconer {q}", f["lightcones"][q][()], ref_stock.lightcones[q])

# ── RSDs (rect, angular plane) ───────────────────────────────────────────────
if not args.no_rsds:
    ropts = dict(opts, rsds=True)
    rout = out.parent / (out.name + "_rsds")
    shutil.rmtree(rout, ignore_errors=True)
    rgeoms = ["rect", "angular_plane"]
    for q in ("brightness_temp", *el.DVDR_INPUTS):
        el.make_quantity(inputs, args.cache, q, rgeoms, rout, ropts, threads=1, clobber=True)
    rlinks = el.finalise(rout, inputs, ropts, clobber=True)
    # tau_21 and the dv/dr-only T_b are set aside and left out of the linked files
    for g in rgeoms:
        aside = all((rout / "intermediate" / g / f"{q}.h5").exists() and not (rout / g / f"{q}.h5").exists()
                    for q in el.NOT_RELEASED)
        with h5py.File(rlinks[g], "r") as f:
            names = sorted(f["lightcones"])
        ok = aside and "tau_21" not in names and "brightness_temp" not in names and \
            {"brightness_temp_with_rsds", "brightness_temp_no_dvdr", "los_velocity"} <= set(names)
        print(f"{g} not-released files set aside, linked {names}: {'ok' if ok else 'FAIL'}")
        if not ok:
            failures.append((f"{g} set aside", str(names)))
    # rerun without clobber: nothing redone, nothing lost; a tau_21 job counts as done
    before = {p: p.stat().st_mtime for p in rout.rglob("*.h5") if p.parent.name in rgeoms}
    el.finalise(rout, inputs, ropts)
    el.make_quantity(inputs, args.cache, "tau_21", rgeoms, rout, ropts, threads=1)
    same = all(p.exists() and p.stat().st_mtime == t for p, t in before.items()
               if p.name not in (f"{g}.h5" for g in rgeoms)) and not (rout / "rect" / "tau_21.h5").exists()
    print(f"finalise and tau_21 rerun keep the files: {'ok' if same else 'FAIL'}")
    if not same:
        failures.append(("rerun", ""))
    # with clobber: the set-aside files come back, are used and go aside again
    rlinks = el.finalise(rout, inputs, ropts, clobber=True)
    again = all((rout / "intermediate" / g / f"{q}.h5").exists() and not (rout / g / f"{q}.h5").exists()
                for g in rgeoms for q in el.NOT_RELEASED)
    print(f"finalise --clobber uses the set-aside files and sets them aside again: {'ok' if again else 'FAIL'}")
    if not again:
        failures.append(("clobber set aside", ""))
    for g in rgeoms:
        lcn = el.lightconers(inputs, g, opts)[g]
        ref = p21c.run_lightcone(lightconer=attrs_evolve(lcn, quantities=("brightness_temp",)),
                                 inputs=inputs, cache=cache, regenerate=False, write=write,
                                 progressbar=False, apply_rsds=True)
        mine = p21c.LightCone.from_file(rlinks[g]) if g == "rect" else None
        with h5py.File(rlinks[g], "r") as f:
            lo = int(f.attrs.get("lowz_buffer_pixels", 0))
            hi = f["lightcones"]["brightness_temp_with_rsds"].shape[-1] - int(f.attrs.get("highz_buffer_pixels", 0))
            for key in sorted(ref.lightcones):
                if key.startswith("brightness_temp") and key in f["lightcones"]:
                    check(f"{g} RSDs {key}", f["lightcones"][key][..., lo:hi], ref.lightcones[key],
                          exact=False)
        if mine is not None:
            print(f"rect RSD file opens with LightCone.from_file: {sorted(mine.lightcones)}")

print("ALL OK" if not failures else f"FAILURES: {failures}")
sys.exit(1 if failures else 0)
