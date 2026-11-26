"""UV luminosity functions of an EOS26 run's galaxies at a few redshifts, for the UV LF figure.

    source envs/use.sh v4.3_post      # tuesday with its UV LF code (PR #141)
    EOS26_TEMPLATE=EOS26_earlyEoR python postprocess/galaxies/uv_luminosity_functions.py
    python postprocess/galaxies/uv_luminosity_functions.py --test --redshifts 6 10

At the node redshifts nearest --redshifts, reads the PerturbedHaloCatalog of galaxy_properties.py
(every galaxy above SAMPLER_MIN_MASS, with the run's feedback), turns it into a tuesday catalogue
and computes its UV luminosity function with tuesday, as tuesday's calculate_uvlf does (the SFRs
and stellar masses of ACGs and MCGs added up), but with K_UV = SFR/L_UV from the BPASS table of
Nikolic et al. (2026) (postprocess/interpolation_table.npy, as in plot_all_summaries.ipynb)
instead of 21cmFAST's constant. Writes <cache>/uv_luminosity_functions.npz (or --out) with
    z, z_request     node redshifts read, and the requested redshifts
    muv_edges        M_UV bin edges [mag] (0.05 mag, -26 to -10)
    counts           galaxies per redshift and M_UV bin, (n_z, n_muv)
    counts_near_min  the same for the galaxies in haloes within --near dex above SAMPLER_MIN_MASS,
                     below which the catalogue has none (for the completeness of the faint end)
    volume           box volume [cMpc^3]
No dust: the figure script applies it, so the dust model can change without reading the
catalogues again. Memory: the whole catalogue of one redshift (~1e9 galaxies at z = 6, ~150 GB).
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from astropy import units as un
from scipy.interpolate import RegularGridInterpolator

HERE = Path(__file__).resolve().parent
sys.path.insert(1, str(HERE.parents[1] / "run_scripts"))
sys.path.insert(1, str(HERE))
import settings  # noqa: E402
from galaxy_properties import output_path  # noqa: E402

MUV_EDGES = np.round(np.arange(-26.0, -9.999, 0.05), 2) * un.mag
TABLE = HERE.parent / "interpolation_table.npy"  # L_UV/SFR on (z, M*, SFR) grids, from Nikolic et al. (2026)


def nikolic26_kuv(sfr, stellar_mass, redshift):
    """K_UV = SFR/L_UV from the BPASS table of Nikolic et al. (2026), for tuesday's sfr_to_uv_magnitude.

    SFR in Msun/yr, stellar mass in Msun; linear interpolation in the table, whose inputs
    are clipped to its range, as in plot_all_summaries.ipynb. Returns Msun/yr / (erg/s/Hz).
    """
    t = np.load(TABLE)
    zs = np.linspace(5, 15, t.shape[0])
    z = float(np.clip(redshift, zs[0], zs[-1]))
    i = min(int(np.searchsorted(zs, z, side="right")) - 1, zs.size - 2)
    w = (z - zs[i]) / (zs[i + 1] - zs[i])
    table = RegularGridInterpolator((np.logspace(3, 13, t.shape[1]), np.logspace(-5, 5, t.shape[2])),
                                    (1 - w) * t[i] + w * t[i + 1])
    return 1 / table(np.column_stack([np.clip(stellar_mass, 1e3, 1e13), np.clip(sfr, 1e-5, 1e5)]))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--redshifts", nargs="+", type=float, default=[6, 8, 10, 11, 12, 14])
    p.add_argument("--test", action="store_true", help="the HII_DIM=200 test run")
    p.add_argument("--near", type=float, default=0.05, help="dex above SAMPLER_MIN_MASS for counts_near_min")
    p.add_argument("--out", default=None, help="output file (default <cache>/uv_luminosity_functions.npz)")
    args = p.parse_args()

    import py21cmfast as p21c
    from py21cmfast.io.h5 import read_output_struct
    from tuesday.core import uv_luminosity_function
    from tuesday.simulators.py21cmfast.catalogs import catalog_from_halo_catalog

    t0 = time.time()
    cache_dir, overrides = settings.inputs_for_run(args.test, False)
    inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
    nodes = np.array(inputs.node_redshifts)
    zs = [float(nodes[np.argmin(np.abs(nodes - z))]) for z in args.redshifts]
    paths = [output_path(cache_dir, inputs, z) for z in zs]
    if missing := [str(q) for q in paths if not q.exists()]:
        sys.exit(f"no PerturbedHaloCatalog files (galaxy_properties.py) at: {missing}")
    near_min = inputs.simulation_options.SAMPLER_MIN_MASS * 10**args.near * un.Msun

    counts, counts_near = [], []
    for z, path in zip(zs, paths):
        catalog = catalog_from_halo_catalog(read_output_struct(path))
        kinds = ["acg", "mcg"] if inputs.astro_options.USE_MCGS else ["acg"]
        catalog = catalog.with_features(
            sfr=sum(catalog[f"sfr_{k}"].astype(np.float64) for k in kinds),
            stellar_mass=sum(catalog[f"stellar_mass_{k}"].astype(np.float64) for k in kinds),
        )
        lf = uv_luminosity_function(catalog, bins=MUV_EDGES, kuv=nikolic26_kuv)
        near = uv_luminosity_function(catalog.select(catalog["halo_mass"] < near_min), bins=MUV_EDGES,
                                      kuv=nikolic26_kuv)
        counts.append(lf.counts)
        counts_near.append(near.counts)
        print(f"[{time.time() - t0:7.1f} s] z = {z:.3f}: {len(catalog)} galaxies, {lf.counts.sum()} in the "
              f"M_UV bins, {near.counts.sum()} of them in haloes below {near_min:.3g}", flush=True)
        del catalog

    out = Path(args.out) if args.out else Path(cache_dir) / "uv_luminosity_functions.npz"
    tmp = out.with_name(out.name + ".part")
    with open(tmp, "wb") as fh:
        np.savez(fh, z=zs, z_request=args.redshifts, muv_edges=MUV_EDGES.value, counts=np.array(counts),
                 counts_near_min=np.array(counts_near),
                 volume=inputs.simulation_options.BOX_LEN ** 3)
    tmp.rename(out)
    print(f"[{time.time() - t0:7.1f} s] wrote {out}")


if __name__ == "__main__":
    main()
