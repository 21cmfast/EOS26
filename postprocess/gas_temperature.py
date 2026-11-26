"""Distribution of the gas temperature (neutral and ionised gas) of an EOS26 run at every node redshift.

    source envs/use.sh v4.3_post
    EOS26_TEMPLATE=EOS26_earlyEoR python postprocess/gas_temperature.py
    python postprocess/gas_temperature.py --test --planes 200

EOS26 runs with MINIMIZE_MEMORY, so its IonizedBox has no kinetic_temperature (the temperature of all the
gas, ionised included); the TsBox has only that of the neutral IGM. This script rebuilds it from the cached
boxes of each node redshift as 21cmFAST's IonisationBox.c computes it (with USE_TS_FLUCT):
  * fully ionised cells (z_reion > 0, x_HI = 0): ComputeFullyIonizedTemperature(z_reion, z, delta, T_RE)
    (thermochem.c; McQuinn 2015, Eq. 6), at least the neutral-gas T_K of the cell;
  * all other cells: T_K x + T_RE (1 - x), with x the neutral fraction before the X-ray ionisation is
    taken off. 21cmFAST subtracts the X-ray x_e filtered on the smallest scale; here x = x_HI + x_e of
    the cell (TsBox xray_ionised_fraction), clipped to [0, 1].
It reads the first --planes planes of the box (default 20: 4.5e7 cells at HII_DIM = 1500) of the IonizedBox
(neutral_fraction, z_reion), PerturbedField (density) and TsBox (kinetic_temp_neutral, xray_ionised_fraction)
and writes <cache>/gas_temperature.npz (or --out) with
    z              node redshifts
    logT_edges     log10 T [K] bin edges (0.02 dex, 0 to 5)
    logrho_edges   log10(1 + delta) bin edges (0.02 dex, -1.5 to 1.5)
    counts         cells per redshift, log T bin and log(1 + delta) bin, (n_z, n_T, n_rho)
    mean_T         mean temperature of the slab cells [K]
    x_HI           mean neutral fraction of the slab cells
    T_RE, planes, HII_DIM
"""
import argparse
import sys
import time
from pathlib import Path

import h5py
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(1, str(HERE.parent / "run_scripts"))
import settings  # noqa: E402

LOGT_EDGES = np.round(np.arange(0.0, 5.0001, 0.02), 2)
LOGRHO_EDGES = np.round(np.arange(-1.5, 1.5001, 0.02), 2)
MIN_DENSITY_LOW_LIMIT = 9e-8  # thermochem.c
TINY = 1e-30  # Constants.h


def fully_ionised_temperature(z_re, z, delta, t_re):
    """21cmFAST's ComputeFullyIonizedTemperature (thermochem.c), for arrays z_re, delta."""
    clip = -1.0 + MIN_DENSITY_LOW_LIMIT
    delta_c = np.maximum(delta, clip)
    delta_re = np.maximum(delta * (1 + z) / (1 + z_re), clip)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        evolved = (((1 + delta_c) / (1 + delta_re)) ** 1.1333 * ((1 + z) / (1 + z_re)) ** 3.4
                   * np.exp(((1 + z) / 7.1) ** 2.5 - ((1 + z_re) / 7.1) ** 2.5))
    just = np.abs(z - z_re) < 1e-4  # ionised at this step: no evolution, and delta not clipped
    result = np.where(just, 1.0, evolved) * t_re**1.7
    result += (1e4 * (1 + z) / 4) ** 1.7 * (1 + np.where(just, delta, delta_c))
    return result**0.5882


def gas_temperature(x_hi, z_reion, delta, t_k, x_e, z, t_re):
    """The temperature of all the gas in each cell, as 21cmFAST's IonisationBox.c (see the module docstring)."""
    x = np.clip(x_hi + x_e, 0.0, 1.0)
    partial = t_k * x + t_re * (1 - x)
    full = (z_reion > 0) & (x_hi < TINY)
    t = partial
    t[full] = np.maximum(fully_ionised_temperature(z_reion[full], z, delta[full], t_re), t_k[full])
    return t


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--test", action="store_true", help="the HII_DIM=200 test run")
    p.add_argument("--planes", type=int, default=20, help="planes of the box read at each redshift (default 20)")
    p.add_argument("--out", default=None, help="output file (default <cache>/gas_temperature.npz)")
    args = p.parse_args()

    import py21cmfast as p21c
    from py21cmfast.io.caching import OutputCache, RunCache

    t0 = time.time()
    cache_dir, overrides = settings.inputs_for_run(args.test, False)
    inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
    run = RunCache.from_inputs(inputs, cache=OutputCache(str(cache_dir)))
    t_re = inputs.astro_params.T_RE
    zs = [z for z in sorted(inputs.node_redshifts) if all(Path(getattr(run, kind)[z]).exists()
                                                         for kind in ("IonizedBox", "PerturbedField", "TsBox"))]
    if not zs:
        sys.exit(f"no node redshift with IonizedBox, PerturbedField and TsBox in {cache_dir}")

    def read(kind, z, field):
        with h5py.File(getattr(run, kind)[z], "r") as f:
            return f[kind]["OutputFields"][field][: args.planes].astype(np.float64)

    counts = np.zeros((len(zs), LOGT_EDGES.size - 1, LOGRHO_EDGES.size - 1), np.int64)
    mean_t, mean_x = np.zeros(len(zs)), np.zeros(len(zs))
    for i, z in enumerate(zs):
        x_hi, z_reion = read("IonizedBox", z, "neutral_fraction"), read("IonizedBox", z, "z_reion")
        delta = read("PerturbedField", z, "density")
        t_k, x_e = read("TsBox", z, "kinetic_temp_neutral"), read("TsBox", z, "xray_ionised_fraction")
        t = gas_temperature(x_hi, z_reion, delta, t_k, x_e, z, t_re)
        counts[i] = np.histogram2d(np.log10(t).ravel(), np.log10(1 + delta).ravel(), [LOGT_EDGES, LOGRHO_EDGES])[0]
        mean_t[i], mean_x[i] = t.mean(), x_hi.mean()
        print(f"[{time.time() - t0:7.1f} s] z = {z:6.3f}: x_HI = {mean_x[i]:.3f}, mean T = {mean_t[i]:9.1f} K, "
              f"{counts[i].sum()} of {t.size} cells in the bins", flush=True)

    out = Path(args.out) if args.out else Path(cache_dir) / "gas_temperature.npz"
    tmp = out.with_name(out.name + ".part")
    with open(tmp, "wb") as fh:
        np.savez(fh, z=zs, logT_edges=LOGT_EDGES, logrho_edges=LOGRHO_EDGES, counts=counts, mean_T=mean_t,
                 x_HI=mean_x, T_RE=t_re, planes=args.planes, HII_DIM=inputs.simulation_options.HII_DIM)
    tmp.rename(out)
    print(f"[{time.time() - t0:7.1f} s] wrote {out}")


if __name__ == "__main__":
    main()
