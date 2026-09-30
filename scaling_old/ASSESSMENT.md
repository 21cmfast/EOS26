# Assessment of the old (v4.2) scaling results — 2026-09-30

**Verdict: re-run everything.** None of the v4.2 numbers here can be used to extrapolate the coeval memory to HII_DIM ≈ 1400–1500. The new harness in `../scaling/` replaces this folder. It is kept only for reference.

## What is in `results/`

| folder | configurations | code | coeval coverage |
|---|---|---|---|
| `gadi_Nthreads_HII_DIM_scaling` | 100 × {1,2,4,8,16}, 200×16, 300×16, 500×{16,32} | mixed | 100–300: full evolution in one call (old code); **500×16: 5/92 coevals**; **500×32: corrupted JSON** |
| `16vs32_HII_DIM_500` | 500 × {16,32} | new (Aug 14) | same two files as above (identical md5) |
| `HII_DIM_500` | 500 × {16,32} | old | 16: full evolution, peak 114.7 GB (106.8 GiB); 32: no coeval phase |
| `HII_DIM_500_scaling` | 500×32 | new | the same corrupted JSON again |
| `jobfs_sameas_scratch` | 200 × {16,32}, jobfs vs scratch | old | full evolution |
| `export_makes_job_serial` | 200×16 with `OMP_PROC_BIND=TRUE` | old | ran on one core |
| `HII_DIM_200_wisdom_scaling` | 200×16, `EOS26_wisdom.toml` (not the production template) | new | 92/92 |
| `mac_scaling` | 100, 200, 300 on the Mac | old | not Gadi |

## Problems

1. **The HII_DIM=500 coeval point covers only 5 of 92 coevals** (97.2 GB), but `reports/README_scaling_values.md` and the fits use it. The fitted HII_DIM=1500 coeval peak (2.41 ± 0.25 TB affine, 1.91 TB power law) is contradicted by production (point 7). The Aug-14 code also deliberately kept a *partial* coeval checkpoint as the result of a resumed job ("A partial coeval checkpoint is already a valid scaling measurement"). That is how partial evolutions ended up in the results.
2. **Corrupted results.** All three `scaling_HII_DIM_500_N_THREADS_32.json` are the same invalid file: a complete JSON followed by the tail of a longer, older one. Every writer used the same `….json.tmp` name, so concurrent or overlapping writes clobbered each other.
3. **The coeval phase contained the PF computation.** The `pf` phase computed a single PF (the lowest redshift). `generate_coeval` then had to compute the other 91 PFs inside the measured coeval phase. Coeval time is inflated by about one PF per coeval, and the coeval memory peak mixes PF computation with the evolution. Production computes all PFs in separate PF jobs.
4. **The coeval loop was not the production loop.** Only z = 5 was requested as an output, so intermediate coevals were released by 21cmFAST's internal purge, which keeps the ICs and halo boxes. `run_N_coevals.py` instead requests every redshift and calls `prepare_for_next_snapshot(force=True)` + `gc.collect()` after each one. Memory behaviour differs.
5. **Possible cache reads instead of computation.** The coeval phase always ran with `regenerate=False`, and the cache was per HII_DIM, shared between N_THREADS values. `scaling_job2.sh` and `scaling_wisdom.sh` never deleted it, and the jobs copied the whole scratch tree (including `scaling/cache`) into jobfs. From the JSON alone, one can't rule out that a coeval measurement read boxes left by an earlier run.
6. **No provenance.** The 21cmFAST version/commit, template hash, host and OpenMP settings were not recorded. (The local `21cmFASTv4.2` clone is v4.2 + 84 commits on `fix_memory_leak`, while the Mac `.venv` has the PyPI 4.2 release, so "v4.2" is ambiguous.) Peaks came from 0.1 s psutil sampling, not an exact high-water mark. The only thread scan was at HII_DIM=100, which is too small to see per-thread memory.
7. **Production contradicts the extrapolation** (`logs/EOS26_coeval_*`, HII_DIM=1500, 16 threads, megamem 2990 GB):
   * first batch, z = 35.4 → 34.0: sampled peak RSS 1.72, 2.04, 2.09 TB;
   * next batch, z = 33.3 → 31.3: 2.16, 2.15, 2.20, 2.25 TB, killed at the 48 h walltime, with PBS "Memory Used" at **2.71 TB**;
   * two later batches that resumed from 7–8 cached coevals were **SIGKILLed at 2.89–2.9 TB** while computing z ≈ 30.0.

   So the coeval memory grows along the evolution, and PBS accounts ~0.45 TB more than the sampled RSS. Resumed batches also need more than the continuous evolution. A small test of the new harness confirms this (v4.2, HII_DIM=40, batches of 30 redshifts): the batched coeval peak was 450 MiB versus 341 MiB continuous, and each batch's peak grew with the number of redshifts it re-established from the cache (290 → 338 → 396 → 450 MiB). The new harness measures all three effects: the full evolution, the cgroup accounting that PBS enforces, and production-like batches (`--coeval-batch`).

## What can still be used

Only as rough sanity checks, not as measurements. The old full-evolution peaks at HII_DIM 200–500 correspond to about 920–970 bytes per HII cell. `../scaling/config.sh` uses that figure only to size the PBS memory requests of the new jobs.
