"""Small extracts of an EOS26 run's lightcones for the paper figures, to copy to a laptop.

    source envs/use.sh v4.3_post
    EOS26_TEMPLATE=EOS26_earlyEoR python postprocess/export_figure_data.py
    python postprocess/export_figure_data.py --redshifts 8 10.8 --maps neutral_fraction --zoom 5

Reads the lightcone stores of postprocess/lightcone/ (rect, full sky, patch) of the run of
$EOS26_TEMPLATE and writes <lightcone dir>/figure_data.h5 (or --out):

    rect/<q>             one plane of the rectilinear lightcone: box cells x = --plane, all y,
                         all slices, (1500, n_slices)
    healpix/<q>          the full-sky maps (Nside 1024, RING) at the slices nearest to
                         --redshifts, (n_z, 12 Nside^2)
    patch/<q>            the patch (Nside 4096) at the same slices, only its pixels within
                         --zoom deg of its centre, (n_z, n_zoom)
    patch/pixels         the RING indices of those pixels
    global_mean/<q>      the box mean at each node redshift (from the rect stores)
    lightcone_redshifts, lightcone_distances, node_redshifts, slice_index, slice_redshift

brightness_temp_dvdr_with_rsds is replaced by brightness_temp (with a message) if finalise
has not made it yet; the datasets carry the name of what was read. The rect planes read
~60 MB per quantity; each full-sky slice reads ~2 GB and each patch slice ~4.6 GB (their
chunks hold 39 slices), so the defaults read ~45 GB and write ~0.5 GB.
"""
import argparse
import sys
import time
from pathlib import Path

import h5py
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(1, str(HERE.parent / "run_scripts"))
sys.path.insert(1, str(HERE / "lightcone"))
import settings  # noqa: E402

import eos_lightcones as el  # noqa: E402

RSD = "brightness_temp_dvdr_with_rsds"

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--dir", default=None, help="lightcone directory (default: that of the run)")
parser.add_argument("--rect", nargs="+", default=[*el.DEFAULT_QUANTITIES, RSD], help="quantities of the rect planes")
parser.add_argument("--maps", nargs="+", default=["density", "neutral_fraction", RSD],
                    help="quantities of the full-sky and patch maps")
parser.add_argument("--redshifts", nargs="+", type=float, default=[8.9, 10.8],
                    help="redshifts of the maps (nearest slices)")
parser.add_argument("--plane", type=int, default=0, help="box index x of the rect plane (default 0)")
parser.add_argument("--zoom", type=float, default=10.0, help="radius of the patch region kept, deg (default 10)")
parser.add_argument("--out", default=None, help="output file (default <lightcone dir>/figure_data.h5)")
args = parser.parse_args()

lc_dir = Path(args.dir) if args.dir else el.default_out_dir(settings.inputs_for_run(False, False)[0])
out = Path(args.out) if args.out else lc_dir / "figure_data.h5"
opts = el.default_options()
t0 = time.time()


def say(msg):
    print(f"[{time.time() - t0:7.1f} s] {msg}", flush=True)


def store(geometry, q):
    """The open store of q in a geometry, and the name of what it holds."""
    d = lc_dir / el.dir_name(geometry, opts)
    for name in (q, "brightness_temp") if q == RSD else (q,):
        if (d / f"{name}.h5").exists():
            h = h5py.File(d / f"{name}.h5", "r")
            if h.attrs.get("complete", False):
                if name != q:
                    say(f"{geometry}: {q} is not made yet (finalise job), using {name}")
                return h, name
            h.close()
    sys.exit(f"no complete {q}.h5 in {d}")


tmp = out.with_name(out.name + ".part")
with h5py.File(tmp, "w") as f:
    f.attrs.update(run=settings.RUN_NAME, plane=args.plane, zoom_deg=args.zoom,
                   healpix_nside=opts["healpix_nside"], patch_nside=opts["patch_nside"],
                   patch_center_deg=opts["patch_center_deg"])
    dist = None
    for q in args.rect:
        h, name = store("rect", q)
        with h:
            if f"rect/{name}" in f:
                continue
            if dist is None:
                dist, z = h["lightcone_distances"][:], h["lightcone_redshifts"][:]
                k = sorted({int(np.argmin(np.abs(z - zz))) for zz in args.redshifts})
                for key, val in (("lightcone_distances", dist), ("lightcone_redshifts", z),
                                 ("node_redshifts", h["node_redshifts"][:]),
                                 ("slice_index", k), ("slice_redshift", z[k])):
                    f[key] = val
            elif h["lightcone_distances"].shape != dist.shape or not np.allclose(h["lightcone_distances"][:], dist):
                sys.exit(f"rect/{name} has other slices than rect/{args.rect[0]}")
            f[f"rect/{name}"] = h["lightcone"][args.plane]
            f[f"global_mean/{name}"] = h["global_mean"][:]
        say(f"rect/{name}")

    if args.maps:
        from astropy.coordinates import angular_separation
        from astropy_healpix import HEALPix

        pix = el.patch_pixels(opts)
        lon, lat = HEALPix(nside=opts["patch_nside"], order="ring").healpix_to_lonlat(pix)
        lon0, lat0 = np.deg2rad(opts["patch_center_deg"])
        keep = np.flatnonzero(angular_separation(lon.to_value("rad"), lat.to_value("rad"), lon0, lat0)
                              <= np.deg2rad(args.zoom))
        f["patch/pixels"] = pix[keep]
        say(f"patch: {keep.size} of {pix.size} pixels within {args.zoom} deg")
    for q in args.maps:
        for geometry in ("healpix", "patch"):
            h, name = store(geometry, q)
            with h:
                if f"{geometry}/{name}" in f:
                    continue
                ds = h["lightcone"]
                # the angular stores can have one slice more than the rect ones (at the far end)
                d = h["lightcone_distances"][:]
                kk = [int(np.argmin(np.abs(d - dist[i]))) for i in k]
                if not np.allclose(d[kk], dist[k]):
                    sys.exit(f"{geometry}/{name} has no slices at the distances of the rect slices {k}")
                if geometry == "patch" and ds.shape[0] != pix.size:
                    sys.exit(f"patch/{name} has {ds.shape[0]} pixels, expected {pix.size}")
                f[f"{geometry}/{name}"] = np.stack([ds[:, j] if geometry == "healpix" else ds[:, j][keep]
                                                    for j in kk])
            say(f"{geometry}/{name} at z = {np.round(z[k], 3).tolist()}")
tmp.rename(out)
say(f"wrote {out} ({out.stat().st_size / 1e6:.0f} MB)")
