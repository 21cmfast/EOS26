import gc
gc.collect()
gc.disable()

import time
import argparse
import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
from compare_EOS import compare_PF
import settings
from settings import now_str, peak_rss_gb

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--z_idx", type=int)
args = parser.parse_args()
z_idx = args.z_idx

logger = settings.setup_logging(args.log_file)


job_start = time.perf_counter()
print(f"[{now_str()}] Starting single PF run: z_idx={z_idx}")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    print(f"[{now_str()}] TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _box_overrides = settings.resolve_run_config(args.test, settings.CACHE_ALT)
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            random_seed=settings.RANDOM_SEED_ALT,
                                            **settings.TEMPLATE_BOX_KWARGS,
                                            **_box_overrides)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
inputs = initial_conditions.inputs  # use the real inputs, with correct node_redshifts
z = inputs.node_redshifts[z_idx]
print(f"[{now_str()}] Running PF at z_idx={z_idx}, z={z:.6f}")

pf = p21c.perturb_field(redshift=z,
                   initial_conditions=initial_conditions,
                   write=True,
                   cache=cache,
                   regenerate=False,
)
compare_PF(pf, z, z_idx)

job_dt = time.perf_counter() - job_start
print(f"[{now_str()}] Completed single PF run in {job_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
    
