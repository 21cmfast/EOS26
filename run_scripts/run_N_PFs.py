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
parser.add_argument("--z_idx_start", type=int)
parser.add_argument("--N", type=int, default=10)
args = parser.parse_args()
z_idx_start = args.z_idx_start
N = args.N

logger = settings.setup_logging(args.log_file)


job_start = time.perf_counter()
print(f"[{now_str()}] Starting N PF run: z_idx_start={z_idx_start}, N={N}")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    print(f"[{now_str()}] TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
    cache_dir, _box_overrides = settings.CACHE_TEST, {"HII_DIM": settings.TEST_HII_DIM}
else:
    _box_overrides = {}
    cache_dir = settings.CACHE_FULL
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
                                            **_box_overrides)
if N == -1:
    N = len(inputs.node_redshifts) - z_idx_start
for i in range(N):
    loop_start = time.perf_counter()
    z_idx = z_idx_start + i
    z = inputs.node_redshifts[z_idx]
    print(f"[{now_str()}] PF {i + 1}/{N}: z_idx={z_idx}, z={z:.6f}")

    pf = p21c.perturb_field(redshift=z,
                   write=True,
                   cache=cache,
                   regenerate=False,
    )
    loop_dt = time.perf_counter() - loop_start
    print(f"[{now_str()}] PF {i + 1}/{N} done in {loop_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
    if not args.test:
        compare_PF(pf, z, z_idx)

job_dt = time.perf_counter() - job_start
print(f"[{now_str()}] Completed N PF run in {job_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
    
