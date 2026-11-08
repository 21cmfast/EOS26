# Lightcones from the cached coevals, one quantity per job

Rectilinear, ring and full-sky HEALPix lightcones of an EOS26 run, made after (or while) the coeval jobs run, straight from the cached boxes. One job per quantity reads that quantity's box once per node redshift and fills every requested geometry in the same pass.

The slices are those of 21cmFAST's `run_lightcone` (`Lightconer.make_lightcone_slices`):

- the same distances;
- the same choice of the two bracketing node redshifts;
- the same linear interpolation in comoving distance;
- the same dv/dr correction of the brightness temperature.

What changes is only the cost. `test_against_21cmfast.py` checks the results against `run_lightcone`; see [Validation](#validation).

|                       | `run_lightcone` (`../make_lightcone.py`, `../make_angular_lightcone.py`) | here |
|-----------------------|-------------------------------------------------------------------|------|
| Reading per redshift   | every array of every struct (~21 × 13.5 GB, for the global means)   | only the quantity's field (13.5 GB, ~25 s) |
| Rectilinear, 1500³     | ~13–14 h per pass, ~0.75 TB RAM                                      | ~40 min per quantity, ~30 GB |
| Ring, 1500³            | ~15 h per quantity (whole box interpolated per slice), +~45 h `los_velocity` | ~1 min on top of the reading |
| Full-sky HEALPix       | not available                                                        | ~3–5 h per quantity on 48 cores at Nside 2048 |
| Resume after a kill    | from the last checkpoint                                             | from the last finished node interval |

## Files

| File | What |
|---|---|
| `lightcone_quantity.py` | CLI: one quantity, any of `--geometry rect ring healpix` |
| `finalise_lightcones.py` | CLI: dv/dr-corrected brightness temperature and the index files |
| `lc_core.py` | the pass over the node redshifts; the `Rect`, `Ring` and `Healpix` geometries |
| `lc_finalise.py` | dv/dr (21cmFAST's `include_dvdr_in_tau21`, in blocks of pixels) and index files |
| `submit_lightcones.sh` | submits one job per quantity (+ HEALPix jobs), then the finalise job |
| `lightcone_job.sh`, `finalise_job.sh` | the PBS jobs |
| `test_against_21cmfast.py` | comparison with `run_lightcone` on a 32³ run |

## Usage (Gadi, from the repository root)

```bash
postprocess/lightcone/submit_lightcones.sh                         # default quantities, rect + ring
postprocess/lightcone/submit_lightcones.sh density neutral_fraction
HEALPIX=1 postprocess/lightcone/submit_lightcones.sh               # + full-sky maps (Nside 2048)
GEOMETRY=healpix NSIDE=1024 postprocess/lightcone/submit_lightcones.sh density
AFTER=<last coeval job id> postprocess/lightcone/submit_lightcones.sh
PARTIAL=1 postprocess/lightcone/submit_lightcones.sh               # fill what is cached now; rerun later for the rest
TEST=1 postprocess/lightcone/submit_lightcones.sh                  # the HII_DIM=200 reference
DRY_RUN=1 postprocess/lightcone/submit_lightcones.sh               # show the qsub commands
```

- **Default quantities:** density, brightness_temp, spin_temperature, neutral_fraction, kinetic_temp_neutral, J_21_LW, sfrd_acg and cumulative_recombinations. These are the eight of `plot_lightcone_square.py`.
- **Brightness temperature:** `brightness_temp` brings `tau_21` and `los_velocity` along, because the dv/dr correction needs them.
- **Logs:** go to `logs/EOS26_lightcone_<quantity>_<geometry>_<jobid>.log`, or to `logs/HII_DIM200_reference/` with TEST=1.
- **Resuming:** resubmit the same command to resume. A file made with other settings stops the job; pass `EXTRA_ARGS=--clobber` to start it again.
- **While the coevals run:** with PARTIAL=1 (`--partial`), node intervals whose boxes are not cached yet are skipped and left NaN, and the files stay `complete = False`. Resubmitting later fills only what is new. The finalise step only uses complete files.
- **Finalise:** the finalise job runs after all per-quantity jobs succeed. Otherwise submit it by hand: `qsub postprocess/lightcone/finalise_job.sh`.

**Without PBS:**

```bash
python postprocess/lightcone/lightcone_quantity.py --quantity density --geometry rect ring --log-file logs/lc.log
python postprocess/lightcone/finalise_lightcones.py --log-file logs/lc_finalise.log
```

## Outputs (`<cache>/lightcones/`)

| Path | Shape | Size per quantity at 1500³, z = 5–35 |
|---|---|---|
| `rect/<q>.h5` | (1500, 1500, 2557) | 23 GB |
| `ring/<q>.h5` | (32768, 2557) | 0.34 GB |
| `healpix_nside<N>/<q>.h5` | (n_shells, 12 N²), shell by shell, RING order by default | 0.13 TB (N=1024), 0.51 TB (2048), 2.06 TB (4096) |
| `<geometry>/brightness_temp_dvdr.h5` | as above | brightness temperature with the dv/dr correction |
| `lightcone_<geometry>_v<version>.h5` | index | external links to every complete quantity file |

**Contents of each per-quantity file:**

- `lightcone`, with NaN where nothing has been written yet;
- `lightcone_distances` (Mpc) and `lightcone_redshifts`;
- `node_redshifts_ascending` and `global_mean` (the box mean at each node; 21cmFAST's `global_quantities`);
- `interval_done`;
- attributes describing the geometry, plus `complete`.

**Index files.** The rect and ring index files have the layout of a 21cmFAST lightcone file, so they open with `p21c.LightCone.from_file`.

- `lightcones/brightness_temp` is the dv/dr-corrected one, as in `run_lightcone`'s output.
- `lightcones/brightness_temp_no_dvdr` is the interpolated coeval field.
- The ring index also has the `ring` group of `make_angular_lightcone.py`, so the square figure works:

  ```bash
  python postprocess/plot_lightcone_square.py --production --lightcone <cache>/lightcones/lightcone_ring_v4.3.1.h5
  ```

## Geometries

- **rect** — 21cmFAST's `RectilinearLightconer.between_redshifts` with the run's cosmology. The line of sight is the box's last axis, with the default `index_offset`, and slices are one cell apart.
- **ring** — the great circle of `make_angular_lightcone.py`: latitude 0, `--n-lon` longitudes (default 2^15, 1.5 cMpc apart at z = 5), seen from the centre of the box, with the box tiled periodically.
- **healpix** — a full-sky map per shell, seen from the centre of the box. Shells are one cell apart by default (`--shell-spacing`).
  - **Pixel averaging:** each pixel is the mean of its 4^oversample NESTED children (`--oversample`, default 1), each sampled trilinearly. Pixels larger than the cells then average the field instead of aliasing it. At z = 5 a cell is 0.66′; at z = 35 it is 0.44′. An Nside 2048 pixel is 1.7′.
  - **Periodic tiling:** the full sky crosses the 2250 Mpc box about 7 times along each axis at z = 5, so structures repeat every L/χ ≈ 16° (less at higher z). Keep that in mind for angular statistics on those scales.
  - **Pixel order:** RING by default (`--order nested` for NESTED).
  - **Cost:** sampling uses threads (`map_coordinates` releases the GIL). At Nside 2048 with oversample 1 that is 2 × 2×10⁸ samples per shell.
  - **dv/dr:** the finalise step assumes shells one cell apart, as 21cmFAST does, and refuses otherwise.

## How it differs from `run_lightcone`

1. **Only the requested field is read.** `run_lightcone` computes the global mean of every field at every node redshift, which reads every array (21cmFAST PR 4 in `bug_reports/21cmFAST_PRs_to_make.md`).
2. **Angular slices are sampled first.** They sample the two bracketing boxes at the pixels, then interpolate those samples in distance. 21cmFAST's `AngularLightconer` instead interpolates the whole box in distance for every slice, then samples it (PR 2).
   - Both steps are linear, so the results agree to rounding.
   - `z_reion`'s "mean_max" rule (taking the larger value where the two boxes differ in sign) works per cell. For it, the rule is evaluated at the 8 cells around each point before they are weighted, which is exactly what sampling 21cmFAST's interpolated box gives.
3. **los_velocity** is `velocity_z` for rect. For ring and HEALPix it is the projection of `velocity_x/y/z` on the line of sight, positive towards the observer, as in cosmotile.
4. **Slices on an interval edge.** Node intervals are processed from high to low redshift, like `run_lightcone`, so a slice on an interval edge gets the same value.

## Validation

`test_against_21cmfast.py` builds the same lightcones twice from a 32³ `minihalos-discrete` run with KEEP_3D_VELOCITIES=True, z = 6–34: once with `p21c.run_lightcone` and once with this code. It compares nine fields plus `tau_21`, `los_velocity`, the dv/dr-corrected brightness temperature and the global means.

Result on 4 November 2026 (21cmFAST 4.3.1, cosmotile 0.2.5): **every array is identical bit for bit** to `run_lightcone`'s.

- **Geometries:** rect (32×32×2208), ring (64 longitudes) and HEALPix (Nside 4, RING order).
- **Arrays:** density, brightness_temp (dv/dr-corrected), spin_temperature, neutral_fraction, z_reion, J_21_LW, sfrd_acg, kinetic_temp_neutral, tau_21, los_velocity, and all global means. That is 57 checks.
- **Index files:** they open with `p21c.LightCone.from_file`.
- **Resume:** calling the script again does nothing, because every interval is already done.
- **Time at 32³:** `run_lightcone` took 67 s (rect), 15 s (ring) and 16 s (HEALPix); this code took 9 s for all three geometries and all ten fields.
- **Oversampling:** with `--oversample 2`, the pixel-to-pixel scatter of density at Nside 4 drops from 0.22 to 0.057. Each pixel then averages 16 directions instead of taking one.

```bash
python postprocess/lightcone/test_against_21cmfast.py --cache /tmp/lc_test   # ~8 min on 2 cores, mostly the coevals
```

## Cost at HII_DIM = 1500

- **Reading:** a 13.5 GB box takes 22–27 s from gdata (production coeval logs). One quantity at 92 node redshifts is ~1.24 TB, so ~40 min.
- **los_velocity:** reads three boxes per redshift for ring and HEALPix (~2 h).
- **Rect and ring:** ~40–60 min per quantity on a part of a normal node, and a few tens of SU.
- **HEALPix:** about 2 × N_dir samples per shell, at ~3.2 M samples/s per core (measured, including the averaging). At Nside 2048 with oversample 1:
  - ~125 core-seconds per shell and ~90 core-hours per quantity;
  - ~3–5 h on a 48-core node plus the reading — how well it scales to 48 threads is not measured yet;
  - `los_velocity` costs 3×.
- **Memory:**
  - two boxes (27 GB), or six for `los_velocity` on ring and HEALPix (81 GB);
  - plus 2.4 GB of HEALPix directions at Nside 2048 with oversample 1 (9.7 GB at Nside 4096).
