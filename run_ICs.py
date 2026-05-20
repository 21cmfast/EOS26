import py21cmfast as p21c
import numpy as np

cache = p21c.OutputCache('/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2000_HIIDIM1200_DIM3600/')

inputs = p21c.InputParameters.from_template("EOS25.toml",
        node_redshifts=p21c.wrapper.inputs.get_logspaced_redshifts(
            min_redshift=5.0,
            z_step_factor=1.02,
            max_redshift=35.0,
        ),
        random_seed=42,
    ) 

print("DONE, Inputs:", inputs)

initial_conditions = p21c.compute_initial_conditions(
    inputs=inputs, cache=cache, write=True
)

for z in inputs.node_redshifts:
    p21c.perturb_field(
    redshift=z, 
    initial_conditions=initial_conditions,
    write=True,cache=cache,
    )
