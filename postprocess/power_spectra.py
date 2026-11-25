"""Spherically averaged power spectra of an EOS26 run's rectilinear lightcones, in chunks along the line of sight.

    source envs/use.sh v4.3_post
    EOS26_TEMPLATE=EOS26_earlyEoR python postprocess/power_spectra.py         # 21-cm signal with RSDs
    python postprocess/power_spectra.py --quantities neutral_fraction density --chunk 300 --step 150

Reads <lightcone dir>/rect/<quantity>.h5 one chunk at a time (the whole 2.25 cGpc face and --chunk cMpc along
the line of sight, 2.3 GB at 382.5 cMpc) and writes <lightcone dir>/power_spectra/<quantity>.npz with
    z         redshift of the middle slice of each chunk
    z_lo, z_hi  redshifts of its first and last slice
    k         bin centres [1/cMpc]
    delta2    dimensionless power Delta^2 = k^3 P / (2 pi^2) per chunk and k bin [unit^2, e.g. mK^2], (n_z, n_k)
    n_modes   modes per bin
The chunks are --chunk cMpc long and start every --step cMpc (defaults 382.5 and 191.25: EOS21's chunk length,
half overlapping). The power spectrum is tuesday's calculate_ps (log k bins, modes with any k_i = 0 left out).
brightness_temp_dvdr_with_rsds is replaced by brightness_temp (with a message) if finalise has not made it.
"""
import argparse
import sys
import time
from pathlib import Path

import astropy.units as un
import h5py
import numpy as np

HERE = Path(__file__).resolve().parent
RSD = "brightness_temp_dvdr_with_rsds"
UNIT = {RSD: un.mK, "brightness_temp": un.mK}  # others dimensionless

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument("--dir", default=None, help="lightcone directory (default: that of the run of $EOS26_TEMPLATE)")
p.add_argument("--quantities", nargs="+", default=[RSD])
p.add_argument("--chunk", type=float, default=382.5, help="chunk length along the line of sight, cMpc")
p.add_argument("--step", type=float, default=191.25, help="distance between chunk starts, cMpc")
p.add_argument("--k-bins", type=int, default=40, help="number of log k bins (default 40)")
p.add_argument("--box", type=float, default=2250.0, help="transverse box size, cMpc (default 2250)")
args = p.parse_args()

if args.dir:
    lc_dir = Path(args.dir)
else:
    sys.path.insert(1, str(HERE.parent / "run_scripts"))
    sys.path.insert(1, str(HERE / "lightcone"))
    import eos_lightcones as el
    import settings

    lc_dir = el.default_out_dir(settings.inputs_for_run(False, False)[0])

from tuesday.core import calculate_ps  # noqa: E402

t0 = time.time()
out_dir = lc_dir / "power_spectra"
out_dir.mkdir(exist_ok=True)
for q in args.quantities:
    for name in (q, "brightness_temp") if q == RSD else (q,):
        path = lc_dir / "rect" / f"{name}.h5"
        if path.exists():
            break
    else:
        sys.exit(f"no {lc_dir / 'rect' / q}.h5")
    if name != q:
        print(f"{q}: not made yet (finalise job), using {name}")
    with h5py.File(path, "r") as h:
        if not h.attrs.get("complete", False):
            sys.exit(f"{path} is not complete")
        ds = h["lightcone"]
        zs = h["lightcone_redshifts"][:]
        n_side, n_slices = ds.shape[0], ds.shape[-1]
        cell = args.box / n_side
        n_chunk, n_step = int(round(args.chunk / cell)), int(round(args.step / cell))
        starts = range(0, n_slices - n_chunk + 1, n_step)
        rows = []
        for i0 in starts:
            chunk = ds[:, :, i0:i0 + n_chunk] * UNIT.get(name, un.dimensionless_unscaled)
            zc = zs[i0 + n_chunk // 2]
            ps1d, _ = calculate_ps(chunk, args.box * un.Mpc, chunk_redshift=zc, calc_2d=False, calc_1d=True,
                                   k_bins=args.k_bins)
            rows.append((zc, zs[i0], zs[i0 + n_chunk - 1], ps1d.k.to_value(1 / un.Mpc), ps1d.ps.value, ps1d.n_modes))
            print(f"{name}: chunk z = {zs[i0]:.2f}-{zs[i0 + n_chunk - 1]:.2f} ({time.time() - t0:.0f} s)", flush=True)
            del chunk
    z, z_lo, z_hi, k, d2, nm = zip(*rows)
    out = out_dir / f"{name}.npz"
    np.savez(out, z=np.array(z), z_lo=np.array(z_lo), z_hi=np.array(z_hi), k=k[0], delta2=np.array(d2),
             n_modes=np.array(nm), unit=str(UNIT.get(name, "")), chunk_cmpc=n_chunk * cell)
    print(f"wrote {out}: {len(z)} chunks, z = {min(z):.2f}-{max(z):.2f}")
