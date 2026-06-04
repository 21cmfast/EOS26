import gc
gc.collect()
gc.disable()

import time
import argparse
import settings

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
parser.add_argument("--z_idx", type=int)
args = parser.parse_args()
z_idx = args.z_idx

logger = settings.setup_logging(args.log_file)

import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
from compare_EOS import compare_PF

job_start = time.perf_counter()
logger.info(f"Starting single PF run: z_idx={z_idx}")
logger.info(f"gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    logger.info(f"TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
    cache_dir, _box_overrides = settings.CACHE_TEST, {"HII_DIM": settings.TEST_HII_DIM}
else:
    _box_overrides = {}
    cache_dir = settings.CACHE_FULL
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            **_box_overrides)
z = inputs.node_redshifts[z_idx]
logger.info(f"Running PF at z_idx={z_idx}, z={z:.6f}")

pf = p21c.perturb_field(redshift=z,
                   write=True,
                   cache=cache,
                   regenerate=False,
)
compare_PF(pf, z, z_idx)

job_dt = time.perf_counter() - job_start
logger.info(f"Completed single PF run in {job_dt:.2f}s")
    
