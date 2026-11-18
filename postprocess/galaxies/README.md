# Galaxy properties of the EOS26 runs

The cached `HaloCatalog` of each node redshift has the halo masses, the Lagrangian halo
positions and the random numbers of the scatter, but no galaxy properties: 21cmFAST computes
them while it grids the halos and does not keep them. `galaxy_properties.py` computes them
again, as the run did (to float32 round-off), and writes one `PerturbedHaloCatalog` per node redshift into
the run's cache. These are the galaxies of the line-intensity maps ([CII], later Hα, [OIII])
and of the galaxy catalogue.

| File | |
|---|---|
| `galaxy_properties.py` | computes and writes the files (resumable) |
| `galaxy_properties_job.sh` | PBS job (hugemem, 16 cpus, 400 GB, 12 h) |
| `test_galaxy_properties.py` | check against 21cmFAST on a 32³ run (~4 min, 1 core) |

## Run

After the coevals of the run (it needs the `TsBox` and `IonizedBox` of every node redshift):

    qsub -v TEST=1 -q normal -l ncpus=4,mem=16gb,walltime=01:00:00 postprocess/galaxies/galaxy_properties_job.sh
    qsub postprocess/galaxies/galaxy_properties_job.sh                                  # EOS26
    qsub -v EOS26_TEMPLATE=EOS26_earlyEoR postprocess/galaxies/galaxy_properties_job.sh

Resubmit to resume. It uses the `v4.3_post` venv (21cmFAST 4.3.2, as the lightcones):
`perturb_halo_catalog` crashes in 4.3.1, and the C code of the two versions is the same.
The memory and time in the job script are estimates; check the peak RSS in the log of the
first job.

## Output

`<cache>/<matter-cosmo hash>/<seed>/<z-grid hash>/<z>/PerturbedHaloCatalog.h5`, next to the
`HaloCatalog.h5` of the same node redshift (21cmFAST's cache path). For every halo above
`SAMPLER_MIN_MASS` (5×10⁹ M☉):

| Array | |
|---|---|
| `halo_coords` | Eulerian position (cMpc, 0 to `BOX_LEN`), from the 2LPT displacement of the ICs |
| `halo_masses` | M☉ |
| `stellar_masses_acg`, `stellar_masses_mcg` | M☉ |
| `sfr_acg`, `sfr_mcg` | M☉ s⁻¹ |
| `n_ion`, `xray_luminosity`, `fesc_weighted_sfr` | 21cmFAST units |

Only the first `n_halos` entries are halos. Node redshifts without halos (EOS26: above
z ≈ 23) have an empty file. About 1 TB per run (2.2×10¹⁰ halos at 44 bytes; 73 GB at z = 5).

    from py21cmfast.io.h5 import read_output_struct
    gal = read_output_struct(path)
    mstar = gal.get("stellar_masses_acg")[: gal.n_halos]

The cache path does not depend on the astrophysical parameters, but the galaxy properties do
(through the feedback on the turnover masses). So these files belong only to the cache of
their own run: `run_scripts/link_upstream.py` links the `HaloCatalog` files, not these, and
the script stops if it finds a file with other input parameters.

## What the test checks

On the 32³ run of `postprocess/lightcone/test_against_21cmfast.py` (minihalos with
Lyman–Werner, relative-velocity and photoheating feedback, as EOS26): the files are at the
cache path, with the halos and masses of the `HaloCatalog`, equal to a direct
`perturb_halo_catalog` call, written again only with `--clobber`; and the `EmissivityFields` recomputed from the cached boxes equal the run's,
with a halo part equal to the gridded galaxy SFRs, n_ion and X-ray luminosities to 1e-5
(float32 positions and grids).
