# EOS26 scaling measurements

This folder measures the **peak memory of each simulation phase** (ICs, PFs, PHFs, coevals) as a function of `HII_DIM` and `N_THREADS`, for 21cmFAST v4.2 and v4.3. The goal is to find the largest `HII_DIM` that fits **safely** on a 3 TB Gadi `megamem` node (2990 GB), and the most efficient `N_THREADS`. Wall time and CPU use are recorded too.

The previous harness lives in `../scaling_old/`. See `../scaling_old/ASSESSMENT.md` for why its v4.2 numbers can't be used for the extrapolation.

## What exactly is measured

Each configuration `(version, HII_DIM, N_THREADS)` runs the four phases in production order. Each phase runs in a **fresh process**, as in production, where each phase is its own job:

| phase    | production script     | what runs                                                                  |
|----------|-----------------------|----------------------------------------------------------------------------|
| `ics`    | `run_ICs.py`          | `compute_initial_conditions`                                               |
| `pf`     | `run_N_PFs.py`        | `perturb_field` at **all 92** node redshifts, one measured step per PF      |
| `phf`    | `run_PHFs.py`         | `evolve_halos` over all node redshifts                                     |
| `coeval` | `run_N_coevals.py`    | `generate_coeval` over **all 92** redshifts (the full astrophysical evolution), one measured step per redshift |

* The py21cmfast calls come from `run_scripts/sim_steps.py`, the same wrappers production uses. The per-step clean-up (`pf.purge()`, `coeval.prepare_for_next_snapshot(force=True)`, `gc.collect()`) and `gc.disable()` also match production.
* **Peak memory** is the kernel's resident-set high-water mark (`VmHWM`). It is reset at every step boundary through `/proc/self/clear_refs`, so both the per-step and the whole-phase peaks are exact, with no sampling gaps. That covers Python, numpy and all of 21cmFAST's C/OpenMP allocations. A 1 s background sampler also writes an RSS time series (`rss/*.csv`) as a cross-check, and the larger of the two values is reported. Off Linux (e.g. macOS), only the sampler is available, and `peak_rss_method` says so.
* **The coeval peak is the maximum over the entire evolution.** Memory grows as halos form. The per-redshift peaks are all stored, so you can see where the maximum occurs.
* **Production-like batches** (`--coeval-batch N`, results in `…_CBNN/`). Production can't run the coeval phase at HII_DIM≈1500 in one job, so `run_N_coevals.py` runs it in batches: each batch is a fresh process that first re-establishes the whole history from the cache. That needs more memory. In a small v4.2 test (HII_DIM=40), the batched peak was 32% above the continuous one, and it grew with every re-established redshift. Both HII_DIM=1500 OOM kills happened in such resumed batches. The campaigns therefore measure a few batched configurations next to the continuous ones. **v4.3 caveat:** at `release-v4.3` 3f028907, resuming a coeval run in a new process segfaults in `setup_radiation_fields`, because the heating tables are never initialised (`bug_reports/2_v4.3_resume_segfault_heat_not_initialised.md`). The earlier `TypeError` (21cmFAST #791) is fixed. So batched v4.3 configurations, and production v4.3 batch jobs, fail until 21cmFAST fixes this, unless the v4.3 venv is built with `V43_PATCH=envs/patches/v4.3_setup_radiation_fields_heat.patch`. Group D is disabled in `campaign_v4.3.sh` for that reason.
* **What PBS sees.** The sampler also records the job's memory *cgroup* (RSS + page cache), which is what PBS accounts and enforces (`cgroup` in the phase JSON, column `cgroup_bytes` in the RSS CSV). PBS's own `resources_used` is saved at the end of each job (`pbs/*.qstat`).
* **No stale caches.** Before a phase is measured, its own products and all downstream products are deleted from the simulation cache. After the phase, every expected product must exist *and* have been written during that attempt, or the phase fails. So a measurement can never be a silent cache read.

## Files

```
scaling/
  campaign_v4.2.sh, campaign_v4.3.sh   the grid of (HII_DIM, N_THREADS) to measure -> launch.sh
  launch.sh                            submits one PBS job per configuration (idempotent)
  job.pbs                              PBS job: modules, OpenMP env, venv -> measure.py
  config.sh                            site settings: project, modules, venv/template per version, resource model
  measure.py                           driver for ONE configuration: resume, lock, state, clean-up
  _worker.py                           measures ONE phase in a fresh process (imports py21cmfast)
  _memory.py, _common.py, _lib.sh      helpers
  summarize.py                         status table + CSV summaries
  templates/EOS26_v4.3.toml            EOS26.toml with the one parameter v4.3 renamed
  results/v4.2/, results/v4.3/         one folder per configuration (below)
  sims/                                simulation caches while a configuration runs (git-ignored)
```

## Running on Gadi

```bash
cd /scratch/qp00/$USER/EOS26
# 0. venvs: v4.2 = the production venv; v4.3 once with
bash envs/create_venv_v4.3.sh gadi               # check sc_venv in scaling/config.sh

# 1. smoke test (a few minutes each)
bash scaling/launch.sh --version v4.2 --pairs 64:4
bash scaling/launch.sh --version v4.3 --pairs 64:4
python3 scaling/summarize.py

# 2. campaigns
bash scaling/campaign_v4.2.sh --dry-run          # see queue/mem/walltime per job
bash scaling/campaign_v4.2.sh
bash scaling/campaign_v4.3.sh

# 3. progress, any time
python3 scaling/summarize.py --label v4.2
```

**Re-run a campaign script whenever you like.** It skips complete configurations and configurations whose job is still queued or running. It (re)submits everything else, and those jobs resume. Automatic retry rules:

* After a SIGKILL (on Gadi, the memory limit), the next submission asks for 50% more memory.
* After a walltime kill, it asks for 50% more walltime (at most 48 h).
* Requests never shrink below the previous submission's.
* A configuration whose unfinished phase has already been attempted 3 times is left alone until you look at it and pass `--retry`.

### Resuming

Resuming always restarts the **first unfinished phase from its beginning**. Completed phases are never measured again. For example, if a job dies during the PHF phase, the next job skips ICs and PFs, wipes the partial halo catalogs, and measures PHFs, then coevals. If products of a completed phase have gone missing (e.g. a scratch purge), measurement restarts from that phase. A resumed configuration must have identical inputs, 21cmFAST version and `sim_steps.py`. Otherwise it refuses to continue (use `--restart`).

### Clean-up

When all four phases of a configuration are complete, its simulation cache (`scaling/sims/<version>/HII_DIM_*_NT_*`) is deleted. Pass `--keep-sim` to keep it. An incomplete configuration always keeps its cache, because resuming needs it.

### Options

`launch.sh` (and the campaign scripts, which forward extra arguments):

| option | meaning |
|---|---|
| `--version v4.2\|v4.3` | selects venv, template and results folder (from `config.sh`) |
| `--dims "…" --threads "…"` / `--pairs "D:N …"` | configurations (cross product and/or explicit pairs) |
| `--phases ics,pf` | measure only these phases (upstream phases are added if needed) |
| `--coeval-batch N` | coevals in production-like batches of N redshifts per process (separate results folder `…_CBNN`) |
| `--keep-sim` | keep the simulation cache after completion |
| `--restart` | archive this configuration's previous results (to `archive/<time>/`) and start over |
| `--mem GB`, `--walltime H:M:S`, `--queue Q` | override the resource model in `config.sh` |
| `--retry` | resubmit configurations that already failed `SC_MAX_ATTEMPTS` (3) times |
| `--dry-run` | print the `qsub` commands only |

`measure.py` also takes `--redo-from PHASE`, which re-measures one phase and everything downstream. It can be run without PBS, e.g. on a laptop:

```bash
source envs/use.sh v4.3
python scaling/measure.py --label v4.3 --template scaling/templates/EOS26_v4.3.toml \
       --hii-dim 64 --n-threads 4 --keep-sim
```

(`HII_DIM` must be at least 34, because `BOX_LEN = 1.5 Mpc × HII_DIM` has to exceed `R_BUBBLE_MAX = 50 Mpc`.)

## Where to look when a job ran (or didn't)

The files appear in this order. Whatever is missing tells you where the job stopped:

1. `pbs/jobids` is written by `launch.sh` at submission (time, job id, resources). If it's the only file, the job hasn't started yet or it died before `job.pbs` got going. Check with `qstat -xf <jobid>` (`job_state`, `Exit_status`, `comment`, `Output_Path`).
2. `pbs/job_<jobid>.log` is written live by `job.pbs` from its first line on: modules, venv checks and all driver output. Use it to see why a job failed before measuring anything.
3. `run.log` and `state.json` are created as soon as `measure.py` starts. `logs/<phase>.attemptN.log` is the live log of the phase that is running.
4. `phases/<phase>.json` is written when a phase completes. `summary.json` is written after every run.
5. `pbs/<submit-time>.out` (PBS's own stdout/stderr plus the resource-usage epilogue) and `pbs/<jobid>.qstat` are only written when the job has ended.

`python3 scaling/summarize.py` lists configurations that never started, with the `qstat -xf` command to run for each.

## Results of one configuration

`results/<version>/HII_DIM_0500_NT_16/`

| file | content |
|---|---|
| `summary.json` | peak RSS, wall time and cores per phase; `max_peak_rss_bytes` and the phase that sets it |
| `phases/<phase>.json` | the measurement: `peak_rss_bytes`, `peak_rss_method`, `baseline_rss_bytes`, `wall_s`, `cpu_s`, `avg_cores`, every step (`redshift`, `peak_rss_bytes`, `wall_s`, `halo_catalog_bytes`, …), `peak_step`, product sizes, host, library versions |
| `phases/<phase>.attemptN.steps.jsonl` | live per-step progress of attempt N (also kept for failed attempts) |
| `rss/<phase>.attemptN.csv` | RSS time series (`elapsed_s, rss_bytes, step`) |
| `logs/<phase>.attemptN.log` | worker log including py21cmfast's own logging |
| `run.log` | driver log across all attempts |
| `state.json` | phase status/attempts plus an event history (which job did what, when) |
| `config.json` | fingerprint (21cmFAST version and commit, template/inputs/`sim_steps.py` hashes, seed, …) and setup info |
| `inputs_full.toml` | fully resolved input parameters of this configuration |
| `pbs/` | `jobids` (every submission), `job_<jobid>.log` (live job log), PBS output `<submit-time>.out`, PBS's own `resources_used` (`<jobid>.qstat`) |

`summarize.py` also writes `results/<version>/summary_phases.csv` (one row per configuration and phase) and `summary_coeval_steps.csv` (peak RSS at every coeval redshift) for the scaling fits.

Only completed phases are ever reported. Partial attempts stay in their `attemptN` files for diagnostics but are never used as measurements.

## Notes

* `baseline_rss_bytes` (about 0.2 GB: Python, py21cmfast and tables) is included in `peak_rss_bytes`, which is the whole process's resident memory, i.e. what must fit on the node.
* The first coeval step includes the generator's set-up (reading ICs, PFs and halo catalogs from the cache), and the first PF includes one-off table initialisation (`includes_setup` / step 0).
* Disk: one configuration peaks at about 7 kB per HII cell (about 0.9 TB at HII_DIM=500). If the whole campaign runs at once, `launch.sh` estimates the total. Check `lquota`.
* Only `config.sh` has site-specific settings (project, modules, venv paths, resource model).
