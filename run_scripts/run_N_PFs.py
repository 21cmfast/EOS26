import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import numpy as np
import argparse
import logging 

logger = logging.getLogger("21cmFAST")
logger.setLevel(logging.DEBUG)

parser = argparse.ArgumentParser()
parser.add_argument("--z_idx_start", type = int)
parser.add_argument("--N", type=int, default=10)
parser.add_argument("--log-file", type=str, required=True)
args = parser.parse_args()
z_idx_start = args.z_idx_start
N = args.N

logger.handlers.clear()
logger.propagate = False
file_handler = logging.FileHandler(args.log_file)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(file_handler)

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200')

inputs = p21c.InputParameters.from_template("EOS25.toml", random_seed=1234)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
inputs = initial_conditions.inputs  # use the real inputs, with correct node_redshifts
for i in range(N):

    z = inputs.node_redshifts[z_idx_start + i]
    print("Current idx:", i, " current z:", z)
    p21c.perturb_field(redshift=z, 
                   initial_conditions=initial_conditions,
                   write=True,
                   cache=cache,
    )
    
