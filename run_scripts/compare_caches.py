"""Compare every coeval field of two runs with the same inputs, redshift by redshift.

    python run_scripts/compare_caches.py REF_CACHE OTHER_CACHE [--test]

For BrightnessTemp, TsBox, IonizedBox and EmissivityFields at every node redshift
present in both: whether the arrays are bit-identical, the largest |difference|, the
largest relative difference (cells where |ref| > 1e-6 of max |ref|), and the relative
difference of the means. Prints the worst redshift per field.
"""
import argparse
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import h5py
import numpy as np
import py21cmfast as p21c
from py21cmfast.io.caching import RunCache

import settings

KINDS = ("BrightnessTemp", "TsBox", "IonizedBox", "EmissivityFields")

ap = argparse.ArgumentParser()
ap.add_argument("ref")
ap.add_argument("other")
ap.add_argument("--test", action="store_true")
args = ap.parse_args()

_, overrides = settings.inputs_for_run(args.test, False)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
rc_ref = RunCache.from_inputs(inputs, cache=p21c.OutputCache(args.ref))
rc_oth = RunCache.from_inputs(inputs, cache=p21c.OutputCache(args.other))


def fields(path, kind):
    with h5py.File(path, "r") as f:
        grp = f[kind]["OutputFields"] if "OutputFields" in f[kind] else f[kind]
        return {k: grp[k][()] for k in grp if isinstance(grp[k], h5py.Dataset) and grp[k].ndim == 3}


worst = {}
n_z = 0
for z in inputs.node_redshifts:
    for kind in KINDS:
        a_p, b_p = Path(getattr(rc_ref, kind)[z]), Path(getattr(rc_oth, kind)[z])
        if not (a_p.exists() and b_p.exists()):
            continue
        fa, fb = fields(a_p, kind), fields(b_p, kind)
        for k in fa:
            a, b = fa[k].astype(np.float64), fb[k].astype(np.float64)
            d = np.abs(a - b)
            big = np.abs(a) > 1e-6 * max(np.abs(a).max(), 1e-300)
            rel = float((d[big] / np.abs(a[big])).max()) if big.any() else 0.0
            mean_rel = abs(a.mean() - b.mean()) / max(abs(a.mean()), 1e-300)
            key = f"{kind}.{k}"
            w = worst.setdefault(key, dict(n=0, identical=0, max_abs=0.0, max_rel=0.0, mean_rel=0.0, z=None))
            w["n"] += 1
            w["identical"] += int(np.array_equal(fa[k], fb[k]))
            if rel >= w["max_rel"]:
                w["max_rel"], w["z"] = rel, round(z, 3)
            w["max_abs"] = max(w["max_abs"], float(d.max()))
            w["mean_rel"] = max(w["mean_rel"], mean_rel)
    n_z += 1

print(f"py21cmfast {p21c.__version__}: {args.other} vs {args.ref}")
print(f"{'field':42s} {'z compared':>10s} {'identical':>9s} {'max |diff|':>11s} {'max rel':>9s} {'at z':>7s} {'mean rel':>9s}")
for key, w in worst.items():
    print(f"{key:42s} {w['n']:10d} {w['identical']:9d} {w['max_abs']:11.3e} {w['max_rel']:9.2e} {str(w['z']):>7s} {w['mean_rel']:9.2e}")
if not worst:
    print("no coeval boxes present in both caches")
