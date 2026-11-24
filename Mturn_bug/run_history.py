"""Reionization history of one box with the installed 21cmFAST version (4.2 or 4.3.x).

    python Mturn_bug/run_history.py --label v4.2               # 300 cMpc box (HII_DIM = 200)
    python Mturn_bug/run_history.py --label v4.3 --hii-dim 86  # 129 cMpc box

The inputs are those of EOS26_earlyEoR.toml (21cmFAST 4.2 parameter names, which 4.3
also reads), with HII_DIM changed and everything else as in the template: 1.5 cMpc
cells, random_seed = 42, N_THREADS = 16, the 92 node redshifts from z = 5 to 35.
Nothing is written to a cache. At every node redshift the script records the box
means of the neutral fraction, of log10 of the ACG and MCG turnover masses used for
the halo emissivities, and of the brightness, spin and kinetic temperatures, the
X-ray ionised fraction and the Lyman-Werner intensity J_21, and writes them to
    Mturn_bug/results/<label>_HIIDIM<HII_DIM>_NT<N_THREADS>.json
which plot_history.py reads. The ACG turnover mass of 21cmFAST <= 4.2 depends on
N_THREADS (see README.md), so runs to be compared should use the same N_THREADS.
"""
import argparse
import json
import re
import tempfile
import time
import warnings
from pathlib import Path

import numpy as np
import py21cmfast as p21c

warnings.simplefilter("ignore")
HERE = Path(__file__).resolve().parent

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--label", required=True, help="name of the run, e.g. v4.2, v4.2fix or v4.3")
ap.add_argument("--template", type=Path, default=HERE.parent / "EOS26_earlyEoR.toml")
ap.add_argument("--hii-dim", type=int, default=200)
ap.add_argument("--n-threads", type=int, default=None, help="default: the template's N_THREADS")
ap.add_argument("--out-dir", type=Path, default=HERE / "results")
args = ap.parse_args()

# The seed and node redshifts are passed explicitly, so the same file works for every 4.x version.
text = args.template.read_text()
seed = int(re.search(r"^random_seed\s*=\s*(\d+)", text, re.M).group(1))
nodes = json.loads(re.search(r"^node_redshifts\s*=\s*(\[.*\])", text, re.M).group(1))
with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as tmp:
    tmp.write("\n".join(l for l in text.splitlines() if not l.startswith(("random_seed", "node_redshifts"))) + "\n")
inputs = p21c.InputParameters.from_template(tmp.name, random_seed=seed, node_redshifts=nodes)
overrides = {"HII_DIM": args.hii_dim}
if args.n_threads:
    overrides["N_THREADS"] = args.n_threads
inputs = inputs.evolve_input_structs(**overrides)
p21c.config["HALO_CATALOG_MEM_FACTOR"] = 2.0  # as run_scripts/sim_steps.py
so = inputs.simulation_options
print(f"21cmFAST {p21c.__version__}: HII_DIM = {so.HII_DIM}, BOX_LEN = {so.BOX_LEN} cMpc, "
      f"N_THREADS = {so.N_THREADS}, seed = {seed}, {len(nodes)} node redshifts", flush=True)


def mean_of(obj, name):
    value = getattr(obj, name, None) if obj is not None else None
    if value is None:
        return float("nan")
    value = getattr(value, "value", value)
    return float(np.mean(np.asarray(value)))


def first_attr(objs, names):
    """First scalar attribute found (the field names differ between 4.2 and 4.3)."""
    for obj in objs:
        for name in names:
            value = getattr(obj, name, None) if obj is not None else None
            if value is not None:
                return float(value)
    return float("nan")


rows, t0 = [], time.time()
out = args.out_dir / f"{args.label}_HIIDIM{so.HII_DIM}_NT{so.N_THREADS}.json"
out.parent.mkdir(parents=True, exist_ok=True)
for coeval, _ in p21c.generate_coeval(inputs=inputs, out_redshifts=[min(nodes)], write=False):
    # 4.2: Coeval.halobox (log10_Mcrit_*_ave); 4.3: Coeval.emissivity_fields (log10_mturn_*_ave)
    boxes = [getattr(coeval, "emissivity_fields", None), getattr(coeval, "halobox", None)]
    rows.append(dict(
        z=float(coeval.redshift),
        xHI=mean_of(coeval.ionized_box, "neutral_fraction"),
        log10_mturn_acg=first_attr(boxes, ["log10_mturn_acg_ave", "log10_Mcrit_ACG_ave"]),
        log10_mturn_mcg=first_attr(boxes, ["log10_mturn_mcg_ave", "log10_Mcrit_MCG_ave"]),
        Tb=mean_of(coeval.brightness_temperature, "brightness_temp"),
        Ts=mean_of(coeval.ts_box, "spin_temperature"),
        Tk=mean_of(coeval.ts_box, "kinetic_temp_neutral"),
        xe=mean_of(coeval.ts_box, "xray_ionised_fraction"),
        J21_LW=mean_of(coeval.ts_box, "J_21_LW"),
        seconds=time.time() - t0,
    ))
    r = rows[-1]
    print(f"z = {r['z']:6.3f}  x_HI = {r['xHI']:.4f}  log10 Mturn ACG = {r['log10_mturn_acg']:.3f}  "
          f"MCG = {r['log10_mturn_mcg']:.3f}  Tb = {r['Tb']:7.2f} mK  {r['seconds']:7.0f} s", flush=True)
    json.dump(dict(label=args.label, version=p21c.__version__, template=args.template.name,
                   HII_DIM=so.HII_DIM, BOX_LEN=so.BOX_LEN, N_THREADS=so.N_THREADS, random_seed=seed,
                   rows=rows), open(out, "w"), indent=1)
print("wrote", out)
