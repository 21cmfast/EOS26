"""Find (and optionally set aside) damaged HDF5 files in a simulation cache.

    python run_scripts/check_cache.py --test                 # the HII_DIM=200 test reference
    python run_scripts/check_cache.py                        # the production cache
    python run_scripts/check_cache.py --test --quarantine    # rename damaged files *.corrupt-<time>
    python run_scripts/check_cache.py --cache-dir DIR --all-files

By default it checks the boxes of the current inputs (EOS26.toml, with the test
overrides for --test): ICs, and per node redshift the PerturbedField, HaloCatalog and
coeval products. --all-files checks every *.h5 below the cache directory instead
(other inputs and versions too). Each file is opened and every group/dataset touched
(sim_steps.h5_problem); a file cut short by a killed job fails this. Quarantined files
are renamed in place, so the run scripts compute those boxes again. Exit status 1 if a
damaged file was found and left in place.
"""
import argparse
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.simplefilter("ignore")
import settings

ap = argparse.ArgumentParser()
ap.add_argument("--test", action="store_true", help="the test reference cache and inputs")
ap.add_argument("--cache-dir", default=None, help="another cache directory (same inputs)")
ap.add_argument("--all-files", action="store_true", help="every *.h5 below the cache directory")
ap.add_argument("--quarantine", action="store_true", help="rename damaged files to *.corrupt-<time>")
args = ap.parse_args()

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache

import sim_steps

cache_dir, overrides = settings.inputs_for_run(args.test, False)
cache_dir = Path(args.cache_dir or cache_dir)

if args.all_files:
    files = sorted(p for p in cache_dir.rglob("*.h5") if p.is_file())
else:
    inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME, **overrides)
    rc = RunCache.from_inputs(inputs, cache=p21c.OutputCache(cache_dir))
    files = [Path(rc.InitialConditions)]
    for kind in ("PerturbedField", "HaloCatalog", "PerturbHaloField", "EmissivityFields",
                 "TsBox", "IonizedBox", "BrightnessTemp", "RadiationFields"):
        files += [Path(p) for p in getattr(rc, kind, {}).values()]
    files = [p for p in files if p.exists()]

print(f"py21cmfast {p21c.__version__}: checking {len(files)} files in {cache_dir}")
counts, bad = Counter(), []
for p in files:
    problem = sim_steps.h5_problem(p)
    counts[(p.stem, problem is None)] += 1
    if problem:
        bad.append((p, problem))
        print(f"DAMAGED {p}\n        {problem}")

for kind in sorted({k for k, _ in counts}):
    print(f"  {kind:18s} ok {counts[(kind, True)]:4d}   damaged {counts[(kind, False)]:4d}")
if not bad:
    print("no damaged files")
    sys.exit(0)
if args.quarantine:
    for p, _ in bad:
        print(f"moved {p.name} -> {sim_steps.quarantine(p).name}  ({p.parent})")
    sys.exit(0)
print(f"{len(bad)} damaged file(s); rerun with --quarantine to set them aside")
sys.exit(1)
