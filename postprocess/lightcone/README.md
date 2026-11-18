# Lightcones of an EOS26 run, made with tuesday

Rectilinear lightcones, the angular plane, full-sky HEALPix maps and a 45° HEALPix patch of an EOS26 run, made from the cached coevals with [tuesday](https://github.com/21cmfast/tuesday) (`tuesday.simulators.py21cmfast`). One job per quantity reads each box it needs once and fills every geometry of the job from it. The files can be filled while the coevals run (`PARTIAL=1`) and resumed after a failure.

The lightconing is tuesday's; this folder only fixes the EOS26 geometries and runs them:

- **Slices:** those of 21cmFAST's `run_lightcone` (one cell apart, interpolated between the two bracketing node redshifts). tuesday's `make_lightcones_on_disk` calls each lightconer's own `make_lightcone_slices`.
- **Angular geometries:** tuesday's `FastAngularLightconer`. It samples the two boxes first and interpolates the samples, and averages each HEALPix pixel over its sub-pixels.
- **dv/dr and RSDs:** 21cmFAST's `include_dvdr_in_tau21` and `apply_rsds`, applied on disk by tuesday.

`test_against_21cmfast.py` checks the results against `run_lightcone` (see [Validation](#validation)).

## Products

At HII_DIM = 1500, z = 5.004–35.06 (2552 slices, 1.5 cMpc apart, EOS26 cosmology; the RSDs need the slices just outside z = 5.01–35).

| Geometry | Folder | Shape | Per quantity | Sampling per quantity |
|---|---|---|---|---|
| `rect` | `rect/` | (1500, 1500, 2552), line of sight = last box axis | 23 GB | none (planes of the box) |
| `angular_plane` | `angular_plane/` | (32768, 2552): longitudes on latitude 0 | 0.33 GB | ~1 core-min |
| `healpix` | `healpix_nside1024/` | (12 582 912, 2552), RING order, each pixel the mean of 16 sub-pixels | 128 GB | ~65–89 core-h |
| `patch` | `patch_nside4096/` | (29 483 660 pixels within 45° of (0°, 0°), 2552), RING order, 4 sub-pixels each | 301 GB | ~52 core-h |

That is 453 GB per quantity and run. The released quantities (decision list, 18 Nov 2026) are the 13 of `DEFAULT_QUANTITIES` and `brightness_temp_dvdr_with_rsds`, so 14 × 453 GB = 6.3 TB per run. While a run is processed, `<out>/intermediate/` holds another 0.9 TB (tau_21 and the dv/dr-only T_b), and each HEALPix job holds its parts next to the joined file until it deletes them (up to 0.43 TB per quantity). `los_velocity` costs 3× the sampling of a scalar field on the angular geometries.

The angular plane lies on the equator of the HEALPix maps, in the same frame, but samples a point every 0.66′ instead of averaging pixels (the equatorial pixels are 5.3′ apart in the full-sky map and 1.3′ in the patch). Each Nside 1024 pixel holds exactly 16 patch pixels, so the patch and the full-sky map can be compared pixel by pixel.

## Choices

All are constants at the top of `eos_lightcones.py`, with command-line overrides. They are the choices of the decision list "EOS26 lightcones: open decisions" (17–18 Nov 2026). All jobs of one run must use the same values, finalise included.

- **Observer:** at the centre of the box.
- **Frame rotation:** none. The angular plane lies in the box plane z = 750, and the HEALPix maps use the box axes. Override: `--rotation 'SEQ:a,b,c'` (scipy Euler angles in degrees, observer frame → box axes); PBS: `ROTATION=...`.
- **Angular plane:** 2^15 longitudes on latitude 0 (0.66′, 1.5 cMpc at z = 5), the full 360°; figures show a wedge.
- **Full sky:** Nside 1024 with 16 sub-pixels 0.86′ apart. No Nside 512 copy (users can average the maps); `finalise_lightcones.py --degrade-nside 512` would make one.
- **Patch:** Nside 4096, 4 sub-pixels 0.43′ apart (below a cell at every z), radius 45° around (0°, 0°), the same pixels on every shell. 45° is ~1.5 HERA FWHM at z = 27 and more at lower z (FWHM ≈ 10° at 150 MHz, scaling as 1/ν; to confirm).
- **Shells:** one cell (1.5 cMpc) apart in comoving distance (110 kHz at z = 5, 89 kHz at z = 8, 45 kHz at z = 35).
- **Rectilinear lightcone:** plain periodic box, z = 5–35. Structure at z = 5 reappears at z ≈ 13.1 at the same transverse position.
- **dv/dr:** applied to the pixel-averaged maps, as in 21cmFAST.
- **RSDs:** on. The lightcones are made on the distances the RSDs need (2–3 more slices at each end), and finalise writes `brightness_temp_dvdr_with_rsds` (T_b with dv/dr and RSDs).
    - This needs node redshifts beyond both ends, so `ZMIN` is 5.01 (the lowest EOS26 node is z = 5.0; the RSDs need 3 cMpc below `ZMIN`).
    - RSDs cannot be added to lightcones made without them. Override: `--no-rsds`; PBS: `RSDS=0`.
- **Released T_b:** `brightness_temp` (no dv/dr, no RSDs) and `brightness_temp_dvdr_with_rsds`. tau_21 and the dv/dr-only T_b are made for finalise only and then set aside in `<out>/intermediate/`.

## Usage (Gadi, from the repository root)

```bash
postprocess/lightcone/submit_lightcones.sh                         # default quantities, all geometries, run EOS26
EOS26_TEMPLATE=EOS26_earlyEoR postprocess/lightcone/submit_lightcones.sh   # the other run
postprocess/lightcone/submit_lightcones.sh density neutral_fraction
GEOMETRY="rect angular_plane" postprocess/lightcone/submit_lightcones.sh   # only some geometries
AFTER=<last coeval job id> postprocess/lightcone/submit_lightcones.sh
PARTIAL=1 postprocess/lightcone/submit_lightcones.sh               # fill what is cached now; rerun later for the rest
TEST=1 postprocess/lightcone/submit_lightcones.sh                  # the HII_DIM=200 test (full sky at Nside 256, patch at 1024)
DRY_RUN=1 postprocess/lightcone/submit_lightcones.sh               # show the qsub commands
```

- **Default quantities:** density, brightness_temp, spin_temperature, neutral_fraction, kinetic_temp_neutral, J_21_LW, sfrd_acg, cumulative_recombinations, los_velocity, ionisation_rate_G12, sfrd_mcg, n_ion and xray_emissivity. brightness_temp brings tau_21 along.
- **Jobs per quantity:**
    - rect + angular plane together: 12 cores, 48 GB; los_velocity 28 cores, 110 GB.
    - The full sky: a whole node, 48 threads, 12 h (los_velocity 36 h).
    - The patch: a whole node, 48 threads, 8 h (los_velocity 24 h).
    - Then one finalise job (24 h), after all of them succeed. Otherwise: `qsub -v EOS26_TEMPLATE=... postprocess/lightcone/finalise_job.sh`.
    - The 48-thread timings are not measured yet: run one quantity first and adjust.
- **Output:**
    - Location: `$EOS26_LIGHTCONE_DIR/<cache name>/`. If that is not set, `/scratch/qp00/$USER/lightcones/<cache name>/` on Gadi, else `<cache>/lightcones/`.
    - NCI removes scratch files that have not been accessed for a long time, so copy the finished products to permanent storage.
- **Logs:** `logs/<run>_lightcone_<quantity>_<geometry>_<jobid>.log`. EOS26's go in `logs/`, other runs' in `logs/<run>/`, and the 200³ test's in `logs/HII_DIM200_reference/`.
- **Resuming:** resubmit the same command. A file made with other settings stops the job; pass `EXTRA_ARGS=--clobber` to start it again.

**Without PBS:**

```bash
source envs/use.sh v4.3_post
python postprocess/lightcone/lightcone_quantity.py --quantity density --geometry rect angular_plane --log-file logs/lc.log
python postprocess/lightcone/finalise_lightcones.py --log-file logs/lc_finalise.log
```

## Environment

The jobs use the venv `v4.3_post` (`source envs/use.sh v4.3_post`), with:

- 21cmFAST 4.3.2 (tuesday needs ≥ 4.3.2), built from source like the v4.3 venv;
- tuesday from GitHub (main has the dv/dr and RSDs on disk, #131 and #134, since 17 Nov);
- cosmotile 0.3.

The coeval jobs keep the v4.3 venv (21cmFAST 4.3.1). 21cmFAST 4.3.2 finds the same cache files: identical paths for EOS26 and EOS26_earlyEoR, full size and 200³, and the 4.3.1 test cache reads with it. Create the venv once on a login node:

```bash
V43_VERSION=4.3.2 V43_VENV=/scratch/qp00/$USER/venvs/EOS26-v4.3_post-intel V43_USE_LABEL=v4.3_post \
V43_UNPIN='cosmotile|powerbox|21cmsense|tuesday-eor' \
V43_EXTRA='tuesday-eor @ git+https://github.com/21cmfast/tuesday@main' \
bash envs/create_venv_v4.3.sh gadi
```

The freeze file it writes records the tuesday commit.

## Files

| File | What |
|---|---|
| `eos_lightcones.py` | The EOS geometries and choices (constants at the top), the per-quantity pass with HEALPix parts in threads, joining the parts, finalise (dv/dr, RSDs, linked files, setting aside what is not released). |
| `lightcone_quantity.py` | CLI: one quantity, any of `--geometry rect angular_plane healpix patch`. |
| `finalise_lightcones.py` | CLI: dv/dr, RSDs and the linked lightcone files. |
| `submit_lightcones.sh` | Submits the per-quantity jobs, then the finalise job. |
| `lightcone_job.sh`, `finalise_job.sh` | The PBS jobs. |
| `test_against_21cmfast.py` | Comparison with `run_lightcone` on a 32³ run. |

## Outputs (`<out>/`)

- `<geometry>/<quantity>.h5`: one tuesday `LightconeStore` per quantity. These are the released files. Each holds:
    - `lightcone` (NaN where not filled yet);
    - the distances and redshifts of the slices;
    - the node redshifts;
    - the mean of each box read (`global_mean`);
    - which intervals are done;
    - a description of the lightconer.
- `<geometry>/brightness_temp_dvdr_with_rsds.h5`: T_b with the dv/dr correction and RSDs.
- `<geometry>.h5`: a 21cmFAST lightcone file (a few kB) that links to the released files of `<geometry>/`. `p21c.LightCone.from_file` reads it, leaving out the slices beyond z = 5.01–35 that only the RSDs need. As in `run_lightcone`'s output, its `brightness_temp_with_rsds` is T_b with dv/dr and RSDs and `brightness_temp_no_dvdr` the T_b without either. The links are relative, so it must stay next to its folder. Also released; no standalone copies.
- `intermediate/<geometry>/`: tau_21 and `brightness_temp_dvdr` (dv/dr only), not released. A rerun of finalise moves them back when it needs them (e.g. with `--clobber`). Delete the folder to save 0.9 TB per run once the products are checked.
- `parts/`: HEALPix parts while a quantity is incomplete. They are joined into `<geometry>/<quantity>.h5` and deleted (`--keep-parts` keeps them).
- The square figure of the angular plane: `python postprocess/plot_lightcone_square.py --production --lightcone <out>/angular_plane.h5` (the file has the layout that script reads; not tried yet).

## Threads and parts

The angular samples come from scipy's `map_coordinates` through cosmotile, one core per call. It releases the GIL: two threads ran 1.93× faster than one in the sandbox.

- **Splitting:** with `--threads N`, a HEALPix geometry is split into N parts of consecutive RING pixels. Each part is a lightconer of its own, filled by its own `make_lightcones_on_disk` call in a thread.
- **Shared boxes:** `SharedFields` reads every box once and keeps the boxes of the last 2–3 node redshifts for all threads (40 GB for a scalar field at 1500³, 122 GB for the three velocities).
- **Joining:** when all parts of a quantity are complete, they are joined. Pixels are independent, so the joined file is the one a single unsplit pass writes (checked bit for bit).
- **Why:** without threads, the full sky at Nside 1024 with 16 sub-pixels takes 65–89 h per quantity, longer than a 48 h job. That is 2 × 2×10⁸ samples per shell at 3.2–4.4 M samples/s.

## Validation

`test_against_21cmfast.py` uses a 32³ `minihalos-discrete` run with KEEP_3D_VELOCITIES=True, z = 6–34, made with 21cmFAST 4.3.1 and read with 4.3.2. It builds the EOS geometries at small sizes, with a generic frame rotation (ZYZ 77°/18°/0°) and patch centre (latitude −30.7°) so that the rotation code is exercised:

- rect;
- an angular plane of 64 longitudes;
- the full sky at Nside 4 with 4 sub-pixels, in 3 parts;
- a 40° patch at Nside 8 with 4 sub-pixels, in 3 parts.

It runs them through `make_quantity` + `finalise`, then compares with `run_lightcone` using the same lightconers.

Result on 18 November 2026 (21cmFAST 4.3.2; tuesday main 699e875, with #131 and #134; cosmotile 0.3.0), 138 checks, all passed:

- **Lightcones:** every lightcone of the 15 fields (the 13 coeval fields of the test, tau_21 and los_velocity; with the dv/dr-corrected `brightness_temp`) is identical bit for bit to `run_lightcone`'s, in all four geometries. This includes ionisation_rate_G12, cumulative_recombinations, sfrd_mcg, n_ion and xray_emissivity.
- **Global means:** equal at the node redshifts the lightcones use. The files have NaN at the 3 nodes outside z = 6–34, which they do not read.
- **Joined parts:** equal bit for bit to one unsplit pass.
- **Nside 2 maps** (averaged from Nside 4, `degrade_nside=2`): match `run_lightcone` at Nside 2 with 16 sub-pixels to 1.6×10⁻⁷ for density, neutral_fraction, z_reion and tau_21. The averaged `brightness_temp` equals tuesday's `degrade` of the Nside 4 map.
- **Angular plane:** tuesday's `FastAngularLightconer` equals 21cmFAST's own `AngularLightconer` bit for bit.
- **RSDs:** `brightness_temp_with_rsds` (rect, angular plane) equals `run_lightcone(apply_rsds=True)` bit for bit.
- **Set aside:** after finalise with RSDs, tau_21 and `brightness_temp_dvdr` are in `intermediate/` and not in the linked files, which hold `brightness_temp_no_dvdr`, `brightness_temp_with_rsds` and the other quantities and open with `LightCone.from_file`. Rerunning finalise, or a tau_21 job, changes nothing; finalise with `--clobber` takes the set-aside files back, uses them and sets them aside again.
- **Index files:** the rect and angular-plane index files open with `LightCone.from_file`. Rerunning a finished quantity does nothing.
- **Boxes read:** each box was read exactly once per quantity (56 node redshifts, 3 fields for los_velocity), with rect + angular plane and 3 + 3 HEALPix parts in 7 threads.
- **Patch pixels:** `patch_pixels` gives the same pixels as tuesday's `disc_pixels` (3 cases, Nside 32–128). It takes 22 s at Nside 4096 for the 45° disc.
- **Defaults:** the constants are the decided values.

The RSD margin was checked separately with the EOS26 template: from `ZMIN` = 5.01 the lightcones start at z = 5.004, inside the lowest node (z = 5.0); `ZMIN` = 5.0 fails.

```bash
python postprocess/lightcone/test_against_21cmfast.py --cache /tmp/lc_test   # ~15 min on 2 cores, plus the coevals if not cached
```
