import gc
gc.collect()
gc.disable()

import time
import argparse
import py21cmfast as p21c
from compare_EOS import compare_ICs, compare_PF
import settings
from settings import now_str, peak_rss_gb

parser = argparse.ArgumentParser()
settings.add_common_args(parser)
args = parser.parse_args()

logger = settings.setup_logging(args.log_file)


job_start = time.perf_counter()
print(f"[{now_str()}] Starting ICs + PFs run")
print(f"[{now_str()}] gc.isenabled() = {gc.isenabled()} (expected: False)")

if args.test:
    print(f"[{now_str()}] TEST MODE: HII_DIM={settings.TEST_HII_DIM}")
cache_dir, _box_overrides = settings.resolve_run_config(args.test, settings.CACHE_FULL)
cache = p21c.OutputCache(cache_dir)

inputs = p21c.InputParameters.from_template(settings.TEMPLATE_NAME,
        **_box_overrides,
    )

print(f"[{now_str()}] Inputs prepared with {len(inputs.node_redshifts)} redshifts")

ics_start = time.perf_counter()
initial_conditions = p21c.compute_initial_conditions(
    inputs=inputs, cache=cache, write=True, regenerate=False,
)
ics_dt = time.perf_counter() - ics_start
print(f"[{now_str()}] Initial conditions done in {ics_dt:.2f}s | peak RSS={peak_rss_gb():.3f} GB")
compare_ICs(initial_conditions)
