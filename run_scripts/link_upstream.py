"""Link the upstream boxes (ICs, PFs, halo catalogs) of a run into another cache directory.

    python run_scripts/link_upstream.py SRC_CACHE DST_CACHE [--test]

Both caches are for the same inputs (EOS26.toml, with the test overrides if --test),
so every box has the same relative path in both; DST gets symlinks to SRC's files.
Coeval products are not linked, so coevals in DST are computed afresh (e.g. with other
run-time settings, see run_scripts/sim_steps.py) while ICs/PFs/halos are only read.
Exits 1 if any upstream box is missing in SRC.
"""
import argparse
import sys
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import py21cmfast as p21c
from py21cmfast.io.caching import RunCache

import settings

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--test", action="store_true")
args = ap.parse_args()

_, overrides = settings.inputs_for_run(args.test, False)
inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
src = RunCache.from_inputs(inputs, cache=p21c.OutputCache(args.src))
dst = RunCache.from_inputs(inputs, cache=p21c.OutputCache(args.dst))

pairs = [(Path(src.InitialConditions), Path(dst.InitialConditions))]
pairs += [(Path(src.PerturbedField[z]), Path(dst.PerturbedField[z])) for z in inputs.node_redshifts]
if inputs.matter_options.has_discrete_halos:
    pairs += [(Path(src.HaloCatalog[z]), Path(dst.HaloCatalog[z])) for z in inputs.node_redshifts]

missing = [s for s, _ in pairs if not s.exists()]
if missing:
    sys.exit(f"{len(missing)} of {len(pairs)} upstream boxes missing in {args.src}, e.g. {missing[0]}")
made = 0
for s, d in pairs:
    if d.exists() or d.is_symlink():
        continue
    d.parent.mkdir(parents=True, exist_ok=True)
    d.symlink_to(s.resolve())
    made += 1
print(f"py21cmfast {p21c.__version__}: linked {made} of {len(pairs)} upstream boxes {args.src} -> {args.dst}")
