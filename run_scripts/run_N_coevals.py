import py21cmfast as p21c
from py21cmfast.io.caching import RunCache
import numpy as np
from template2input import create_params_from_template
from py21cmfast import generate_coeval
import gc

#p21c.config['HALO_CATALOG_MEM_FACTOR'] = 2.

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200')

inputs = p21c.InputParameters.from_template("EOS25.toml", random_seed=1234)
runcache = RunCache.from_inputs(inputs, cache=cache)
initial_conditions = runcache.get_ics()
# use the real inputs, with correct node_redshifts
inputs = p21c.InputParameters.from_template("EOS25.toml", 
                                            random_seed=1234,
                                            node_redshifts=initial_conditions.inputs.node_redshifts)  


count = 0
for coeval, _ in p21c.generate_coeval(
    inputs = inputs,
    regenerate = False,
    write = True,
    cache = cache,
    initial_conditions = initial_conditions,
    progressbar = True,
):
    print("One coeval done")
    count += 1
    if count == 9:
        break

    
