"""Finish the per-quantity lightcones of postprocess/lightcone/ (library; CLI: finalise_lightcones.py).

* dv/dr: brightness_temp_dvdr = 21cmFAST's rsds.include_dvdr_in_tau21 applied to the
  brightness_temp, tau_21 and los_velocity lightcones, exactly what run_lightcone does at
  its last redshift by default (include_dvdr_in_tau21=True, apply_rsds=False). The
  correction only involves the line of sight, so it is done in blocks of pixels.
* index files: one file per geometry that links (HDF5 external links, no copies) to the
  per-quantity files. For rect and ring it has the layout of a 21cmFAST lightcone file
  (attrs, lightcones/<q>, global_quantities/<q>, lightcone_distances, InputParameters),
  where lightcones/brightness_temp is the dv/dr-corrected one, as in run_lightcone's
  output, and lightcones/brightness_temp_no_dvdr the interpolated coeval field. The ring
  file also has the 'ring' group of make_angular_lightcone.py, so plot_lightcone_square.py
  can read it with --lightcone.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import h5py
import numpy as np

log = logging.getLogger("21cmFAST")

DVDR = "brightness_temp_dvdr"


def _complete(path: Path) -> bool:
    if not path.exists():
        return False
    with h5py.File(path, "r") as f:
        return bool(f.attrs.get("complete", False))


def dvdr_inputs(geom_dir: Path, inputs) -> list[Path]:
    names = ["brightness_temp", "los_velocity"]
    if inputs.astro_options.USE_TS_FLUCT:
        names.append("tau_21")
    return [geom_dir / f"{n}.h5" for n in names]


def make_dvdr(geom_dir: Path, inputs, block_bytes: float = 2e9, clobber: bool = False) -> Path | None:
    """brightness_temp_dvdr.h5 next to its inputs (None if they are not all complete)."""
    from py21cmfast.rsds import include_dvdr_in_tau21

    need = dvdr_inputs(geom_dir, inputs)
    if not all(_complete(p) for p in need):
        log.info(f"{geom_dir.name}: no dv/dr correction, missing or incomplete: "
                 f"{[p.name for p in need if not _complete(p)]}")
        return None
    out = geom_dir / f"{DVDR}.h5"
    if _complete(out) and not clobber:
        log.info(f"{out} exists")
        return out
    ts = inputs.astro_options.USE_TS_FLUCT
    with h5py.File(need[0], "r") as fb, h5py.File(need[1], "r") as fv, \
            (h5py.File(need[2], "r") if ts else _Null()) as ft:
        geometry = fb.attrs["geometry"]
        shell_major = geometry == "healpix"
        if shell_major and not np.isclose(fb.attrs["shell_spacing_mpc"],
                                          inputs.simulation_options.cell_size.value):
            raise ValueError("21cmFAST's dv/dr correction assumes slices one cell apart; "
                             f"{geom_dir} has shells every {fb.attrs['shell_spacing_mpc']} Mpc")
        z = fb["lightcone_redshifts"][()]
        bt, vel = fb["lightcone"], fv["lightcone"]
        tau = ft["lightcone"] if ts else None
        with h5py.File(out, "w") as fo:
            for k, v in fb.attrs.items():
                fo.attrs[k] = v
            fo.attrs["quantity"] = DVDR
            fo.attrs["complete"] = False
            fo.attrs["about"] = ("brightness_temp with 21cmFAST's include_dvdr_in_tau21 "
                                 "(periodic=False), from brightness_temp, tau_21 and los_velocity")
            for k in ("lightcone_distances", "lightcone_redshifts", "node_redshifts_ascending",
                      "longitude", "latitude"):
                if k in fb:
                    fb.copy(k, fo)
            dso = fo.create_dataset("lightcone", shape=bt.shape, dtype=np.float32,
                                    chunks=bt.chunks, fillvalue=np.nan)
            # blocks over the pixel axis (axis 0, or 1 for the shell-major HEALPix maps)
            axis = 1 if shell_major else 0
            per_row = int(np.prod(bt.shape)) // bt.shape[axis]
            step = max(1, int(block_bytes // (8 * per_row)))
            if bt.chunks and bt.chunks[axis] > 1:
                step = max(bt.chunks[axis], (step // bt.chunks[axis]) * bt.chunks[axis])
            for a in range(0, bt.shape[axis], step):
                sl = (slice(None), slice(a, a + step)) if shell_major else (slice(a, a + step),)
                b, v = bt[sl], vel[sl]
                t = tau[sl] if ts else None
                if shell_major:  # line of sight last, as 21cmFAST expects
                    b, v = b.T, v.T
                    t = t.T if ts else None
                res = include_dvdr_in_tau21(brightness_temp=b, los_velocity=v, redshifts=z,
                                            inputs=inputs, periodic=False, tau_21=t)
                res = np.asarray(getattr(res, "value", res), dtype=np.float32)
                dso[sl] = res.T if shell_major else res
            fo["global_mean"] = np.full(len(fb["global_mean"]), np.nan)
            fo["interval_done"] = fb["interval_done"][()]
            fo.attrs["complete"] = True
    log.info(f"{out}: done")
    return out


class _Null:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def write_index(geom_dir: Path, inputs, out: Path | None = None) -> Path | None:
    """One file per geometry linking every complete per-quantity file (see module docstring)."""
    from py21cmfast.io import h5 as p21h5

    files = sorted(p for p in geom_dir.glob("*.h5") if _complete(p))
    if not files:
        return None
    with h5py.File(files[0], "r") as f0:
        geometry = f0.attrs["geometry"]
        version = f0.attrs["py21cmfast_version"]
        name = geom_dir.name
    out = out or geom_dir.parent / f"lightcone_{name}_v{version}.h5"
    names = {p.stem: p for p in files}
    links = dict(names)
    if DVDR in names:  # as run_lightcone: brightness_temp is the dv/dr-corrected one
        links["brightness_temp"] = names[DVDR]
        links.pop(DVDR)
        if "brightness_temp" in names:
            links["brightness_temp_no_dvdr"] = names["brightness_temp"]
    # node order of 21cmFAST's global_quantities: inputs.node_redshifts
    node_z = np.asarray(inputs.node_redshifts, dtype=float)
    with h5py.File(out, "w") as fl:
        fl.attrs["lightcone"] = True
        fl.attrs["last_completed_node"] = len(node_z) - 1
        fl.attrs["last_completed_lcidx"] = 0
        fl.attrs["lowz_buffer_pixels"] = 0
        fl.attrs["highz_buffer_pixels"] = 0
        fl.attrs["__version__"] = version
        fl.attrs["geometry"] = geometry
        fl.attrs["about"] = ("Index of postprocess/lightcone/ outputs: datasets are external links "
                             "to the per-quantity files in " + name + "/")
        fl.create_group("photon_nonconservation_data")
        grp = fl.create_group("maps" if geometry == "healpix" else "lightcones")
        glob = fl.create_group("global_quantities")
        for q, p in sorted(links.items()):
            grp[q] = h5py.ExternalLink(os.path.relpath(p, out.parent), "/lightcone")
            with h5py.File(p, "r") as f:
                za = f["node_redshifts_ascending"][()]
                gm = f["global_mean"][()]
            # global means of the coeval fields (the dv/dr file has none: its
            # brightness_temp entry is the coeval mean, as in 21cmFAST)
            key = "brightness_temp" if q == "brightness_temp_no_dvdr" else q
            if np.isfinite(gm).any() and key not in glob:
                order = [int(np.argmin(np.abs(za - z))) for z in node_z]
                glob[key] = gm[order]  # in inputs.node_redshifts order, like 21cmFAST
        with h5py.File(files[0], "r") as f0:
            for k in ("lightcone_distances", "lightcone_redshifts"):
                f0.copy(k, fl)
            if geometry == "ring":
                ring = fl.create_group("ring")
                ring["longitude"] = f0["longitude"][()]
                ring["latitude"] = f0["latitude"][()]
                ring.attrs["origin_pixels"] = f0.attrs["origin_pixels"]
            if geometry == "healpix":
                hp = fl.create_group("healpix")
                for k in ("nside", "oversample", "order", "shell_spacing_mpc", "origin_pixels"):
                    hp.attrs[k] = f0.attrs[k]
    p21h5._write_inputs_to_group(inputs, out)
    log.info(f"{out}: {sorted(links)}")
    return out
