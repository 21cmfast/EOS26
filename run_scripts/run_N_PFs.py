import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import numpy as np
import argparse
import logging 

logger = logging.getLogger("21cmFAST")
logger.setLevel(logging.DEBUG)

parser = argparse.ArgumentParser()
parser.add_argument("--z_idx_start", type = int)
z_idx_start = parser.parse_args().z_idx_start

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200')

inputs = p21c.InputParameters.from_template("EOS25.toml", random_seed=1234)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
inputs = initial_conditions.inputs  # use the real inputs, with correct node_redshifts
for i in range(10):

    z = inputs.node_redshifts[z_idx_start + i]
    print("Current idx:", i, " current z:", z)
    p21c.perturb_field(redshift=z, 
                   initial_conditions=initial_conditions,
                   write=True,
                   cache=cache,
    )
    
