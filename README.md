# EOS26
## Description
All scripts to run the EOS26 simulation with 21cmFASTv4.2.
EOS26 is run phase by phase i.e. ICs first, then PFs, then PHFs, and finally coevals.

## How to run
All scripts accept an optional `--test` flag to run a small test box (HII_DIM=200).

### Comparison workflow

- Generate the reference once with `--test` and no `--compare`. It is written to
`EOS26_test_HIIDIM200/`.
- Run the production workflow with `--compare` to check
each output against that reference.
- For a local workflow check, use both flags:
`--test --compare`. Candidate files then go to
`EOS26_test_HIIDIM200_compare/`, so the reference is never overwritten. Both
test modes use the same input parameters and random seed (`42`).

### End-to-end test
- `sbatch sbatch_scripts/full_test_job.sh` — runs all three pipeline steps sequentially in test mode.
- `qsub pbs_scripts/full_test_job.sh` — PBS equivalent of the end-to-end test.

### Scaling Measurements

- Run `bash scaling/scaling_job.sh` to measure the default `HII_DIM=200` and
`HII_DIM=300` cases. Each run disables garbage collection, records peak process
RSS with `psutil`, and amortizes the full node-redshift coeval evolution over its
outputs, then writes a phase-by-phase JSON record under
`scaling/results/`. To benchmark other dimensions, pass them as arguments, for
example `bash scaling/scaling_job.sh 200 300 400`.

- After at least two measurements, `scaling/run_scalingrelation.py` fits power
laws for time, peak memory, phase storage, and every stored HDF5 structure. It
writes plots, `README_scaling_values.md`, and `scaling_fits.json` to
`scaling/reports/`. The generated Markdown file is the source for updating the
scaling table below. To apply direct measurements from the smallest and largest
completed `HII_DIM` runs plus fitted extrapolation intervals from every available
scaling result, run `uv run --no-sync scaling/run_scalingrelation.py
--update-readme`; it relabels the two measured columns and updates both EOS
extrapolation sections.

### Production run (in order)
1. **Initial conditions (ICs):**
   - `sbatch sbatch_scripts/ICs_job.sh [--test]`
  - `qsub pbs_scripts/ICs_job.sh [--test]` on PBS.
   - Writes `EOS26.toml` (full template with embedded node redshifts and random seed) and `EOS26_minimal.toml`, then runs `run_scripts/run_ICs.py`.
2. **Perturbed fields (PFs):**
   - `bash sbatch_scripts/submit_PF_jobs.sh [--test]` — submits one job per PF (indices 0–91) (not used for production).
   - `sbatch sbatch_scripts/N_PF_job.sh <z_idx> [N] [--test]` — runs a batch of N PFs (default N=10) starting from redshift index `z_idx`.
  - `bash pbs_scripts/submit_PF_jobs.sh [--test]` and `qsub pbs_scripts/N_PF_job.sh <z_idx> [N] [--test]` are the PBS equivalents.
3. **Perturbed halo fields (PHFs):**
   - `sbatch sbatch_scripts/PHFs_job.sh [--test]` — runs `run_scripts/run_PHFs.py`.
  - `qsub pbs_scripts/PHFs_job.sh [--test]` on PBS.
4. **Coevals:**
   - `sbatch sbatch_scripts/N_coeval_job.sh [N] [--test]` — runs a batch of N coevals (default N=10) with `run_scripts/run_N_coevals.py`.
  - `qsub pbs_scripts/N_coeval_job.sh [N] [--test]` on PBS.
## Table

<table><thead>
  <tr>
    <th>EOS26 simulation step<br></th>
    <th colspan="2">Computation time [hrs]</th>
    <th colspan="2">Memory [Tb]</th>
    <th colspan="2">Storage [Tb]</th>
    <th colspan="2">SUs</th>
  </tr></thead>
<tbody>
  <tr>
    <td></td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
    <td>Estimated</td>
    <td>Actual</td>
  </tr>
  <tr>
    <td>Initial conditions</td>
    <td>13.5 + 2.75 <br>for writing to disk<br><br></td>
    <td></td>
    <td>1.1</td>
    <td>1.3</td>
    <td>652 Gb</td>
    <td>747 Gb</td>
    <td></td>
    <td>864 EM <br> for ICs + PFs<br></td>
  </tr>
  <tr>
    <td>One perturbed field<br></td>
    <td>0.6<br></td>
    <td></td>
    <td>25 Gb<br></td>
    <td>26 Gb</td>
    <td>25Gb x 92 = 2.3Tb</td>
    <td>2.4Tb</td>
    <td></td>
    <td></td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>22 hrs</td>
    <td></td>
    <td>0.71</td>
    <td>0.77</td>
    <td>~330 G</td>
    <td>33 G</td>
    <td>720 EM</td>
    <td>617 EM</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>7</td>
    <td></td>
    <td>3.65</td>
    <td></td>
    <td>2.6Tb x 92 = 240 Tb<br>0.215 x 92 = 20Tb without XRS<br></td>
    <td></td>
    <td>672 EM x 92 = 62k</td>
    <td></td>
  </tr>
</tbody></table>

## Scaling test results

When updated with `--update-readme`, each extrapolated value is the mean ± 1σ from all available scaling points. Each extrapolated quantity shows both its current model (affine `overhead + coefficient * HII_DIM^3` for peak RSS; free-exponent power law for time and storage) and a fixed-cubic `a=3` fit. The regression uncertainty is combined in quadrature with a fixed 10% relative measurement-uncertainty floor. EOS-1: HII\_DIM = 1400 (1.5 cMpc/cell, 2100 Mpc). EOS-2: HII\_DIM = 1200 (1.667 cMpc/cell, 2000 Mpc). Storage for PFs and coevals is the total across all 92 node redshifts; coeval storage includes retained IonizedBox and excludes transient XraySourceBox.

<table><thead>
  <tr>
    <th>EOS26 simulation step</th>
    <th colspan="2">Computation time [hrs]</th>
    <th colspan="2">Memory</th>
    <th colspan="2">Storage</th>
  </tr>
  <tr>
    <th></th>
    <th>N=100</th>
    <th>N=500</th>
    <th>N=100</th>
    <th>N=500</th>
    <th>N=100</th>
    <th>N=500</th>
  </tr>
</thead>
<tbody>
  <tr><td colspan="7"><em>Scaling tests (measured)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td>0.0374</td>
    <td>0.624</td>
    <td>0.939 GB</td>
    <td>97.2 GB</td>
    <td>0.464 GB</td>
    <td>58 GB</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td>0.0345</td>
    <td>0.0447</td>
    <td>0.334 GB</td>
    <td>20.2 GB</td>
    <td>0.016 GB</td>
    <td>2 GB</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>0.0498</td>
    <td>0.659</td>
    <td>0.564 GB</td>
    <td>51 GB</td>
    <td>0.207 GB</td>
    <td>25.4 GB</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>0.00199</td>
    <td>0.423</td>
    <td>1.16 GB</td>
    <td>97.2 GB</td>
    <td>0.0601 GB x 92 = 5.53 GB</td>
    <td>n/a (partial run: 5/92 coevals)</td>
  </tr>
  <tr><td colspan="7"><em>Extrapolated to EOS (HII_DIM = 1400, 1.5 cMpc/cell, 2100 Mpc)</em></td></tr>
  <tr>
    <td>Initial conditions</td>
    <td>a=1.72: 2.7 ± 1.89</td>
    <td>a=3: 13.8 ± 1.49</td>
    <td>affine (overhead + a=3): 2.13 ± 0.213 TB</td>
    <td>a=3: 2.13 ± 0.213 TB</td>
    <td>a=3: 1.27 ± 0.122 TB</td>
    <td>a=3: 1.27 ± 0.127 TB</td>
  </tr>
  <tr>
    <td>One perturbed field</td>
    <td>a=0.152: 0.0495 ± 0.00718</td>
    <td>a=3: 1.15 ± 0.676</td>
    <td>affine (overhead + a=3): 0.439 ± 0.0439 TB</td>
    <td>a=3: 0.444 ± 0.0445 TB</td>
    <td>a=3: 0.0438 ± 0.00418 TB</td>
    <td>a=3: 0.0439 ± 0.00439 TB</td>
  </tr>
  <tr>
    <td>Perturbed halo fields</td>
    <td>a=1.6: 2.54 ± 1.9</td>
    <td>a=3: 14.7 ± 1.69</td>
    <td>affine (overhead + a=3): 1.12 ± 0.112 TB</td>
    <td>a=3: 1.12 ± 0.112 TB</td>
    <td>a=2.99: 0.549 ± 0.0527 TB</td>
    <td>a=3: 0.558 ± 0.0558 TB</td>
  </tr>
  <tr>
    <td>Evolving astrophysics for one coeval</td>
    <td>a=3.26: 8.76 ± 5.98</td>
    <td>a=3: 9.03 ± 1.11</td>
    <td>affine (overhead + a=3): 2.1 ± 0.217 TB</td>
    <td>a=3: 2.15 ± 0.221 TB</td>
    <td>a=3: 0.164 ± 0.0157 TB x 92 = 15.1 ± 1.44 TB</td>
    <td>a=3: 0.165 ± 0.0165 TB x 92 = 15.1 ± 1.51 TB</td>
  </tr>
</tbody></table>


## EOS Fixed-Cubic Runtime Plan

Planning values use fixed `a=3` central estimates at `HII_DIM=1400`, a 1.5 h IC-read allowance per dependent job, and the documented 3 h IC-write time to infer output-write throughput. Coeval output includes retained `IonizedBox` and excludes transient `XraySourceBox`. The table uses the 24 h maximum job walltime; coeval jobs are deliberately limited to 4 outputs for margin. Peak RSS is the per-phase process estimate; full-phase output totals all 92 PFs or coevals as applicable.

| Phase | Work unit | Units/job | Compute/unit [h] | IC read/job [h] | Write/unit [h] | Estimated job walltime [h] | Jobs for full phase | Serial phase walltime [h] | Peak RSS [TB] | Output, full phase [TB] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Initial conditions | all ICs | 1 | 13.80 | 0.00 | 3.00 | 16.80 | 1 | 16.8 | 2.13 | 1.16 |
| Perturbed fields | one PF | 17 | 1.15 | 1.50 | 0.10 | 22.87 | 6 | 137.2 | 0.44 | 3.67 |
| Perturbed halo fields | all halo fields | 1 | 14.70 | 1.50 | 1.31 | 17.52 | 1 | 17.5 | 1.12 | 0.51 |
| Coevals | one coeval | 4 | 9.03 | 1.50 | 0.39 | 39.16 | 23 | 900.7 | 2.15 | 13.78 |
