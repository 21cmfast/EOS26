#!/usr/bin/env python3
"""Time 21cmFAST's FFTs with FFTW_ESTIMATE (USE_FFTW_WISDOM = false) and with saved wisdom.

    python scaling/bench_fft_wisdom.py --threads 16 --sizes 300 400 500 1500
    python scaling/bench_fft_wisdom.py --threads 16 --sizes 300 --wisdoms DIR --repeat 5

Does what dft_r2c_cube / dft_c2r_cube in 21cmFAST's dft.c do: an in-place 3D r2c, then
c2r, FFT of an fftwf_malloc'd n^3 box, each plan made right before its FFT and destroyed
right after, with FFTW_ESTIMATE, or with FFTW_WISDOM_ONLY after importing the files
21cmFAST's CreateFFTWWisdoms saves (<wisdoms>/{r2c,c2r}_DIM<n>_DIM<n>_NTHREADS<t>;
default <DATA_ROOT>/fftw_wisdoms, as in run_scripts/sim_steps.py). Uses the FFTW
libraries py21cmfast's C extension is linked against. The rounds go estimate, wisdom,
estimate, wisdom, so node drift shows up as a difference between rounds of one mode.
Memory: 8 n^2 (n/2+1) bytes, 13.5 GB at n = 1500.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import py21cmfast.c_21cmfast  # noqa: F401  (loads the FFTW libraries it is linked against)

FFTW_ESTIMATE = 1 << 6
FFTW_WISDOM_ONLY = 1 << 21

fftw = ctypes.CDLL("libfftw3f.so.3")  # by soname: the copies already loaded
omp = ctypes.CDLL("libfftw3f_omp.so.3")
fftw.fftwf_malloc.restype = ctypes.c_void_p
fftw.fftwf_malloc.argtypes = [ctypes.c_size_t]
fftw.fftwf_free.argtypes = [ctypes.c_void_p]
for name in ("fftwf_plan_dft_r2c_3d", "fftwf_plan_dft_c2r_3d"):
    f = getattr(fftw, name)
    f.restype = ctypes.c_void_p
    f.argtypes = [ctypes.c_int] * 3 + [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
fftw.fftwf_execute.argtypes = [ctypes.c_void_p]
fftw.fftwf_destroy_plan.argtypes = [ctypes.c_void_p]
fftw.fftwf_import_wisdom_from_filename.argtypes = [ctypes.c_char_p]
omp.fftwf_plan_with_nthreads.argtypes = [ctypes.c_int]


def one_fft(kind: str, n: int, box: int, flag: int) -> float:
    t0 = time.perf_counter()
    plan = getattr(fftw, f"fftwf_plan_dft_{kind}_3d")(n, n, n, box, box, flag)
    if not plan:
        raise LookupError(f"no {kind} plan for n={n} in the imported wisdom")
    fftw.fftwf_execute(plan)
    fftw.fftwf_destroy_plan(plan)
    return time.perf_counter() - t0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", type=int, nargs="+", required=True)
    ap.add_argument("--threads", type=int, required=True)
    ap.add_argument("--repeat", type=int, default=3, help="r2c+c2r pairs per round (default 3)")
    ap.add_argument("--wisdoms", type=Path, default=None)
    args = ap.parse_args()
    if args.wisdoms is None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "run_scripts"))
        import settings

        args.wisdoms = Path(os.environ.get("EOS26_WISDOMS") or Path(settings.DATA_ROOT) / "fftw_wisdoms")
    nt = args.threads
    omp.fftwf_init_threads()
    omp.fftwf_plan_with_nthreads(nt)
    print(f"FFTW threads {nt}, wisdom files from {args.wisdoms}, {args.repeat} pairs per round", flush=True)
    rows = []
    for n in args.sizes:
        files = [args.wisdoms / f"{k}_DIM{n}_DIM{n}_NTHREADS{nt}" for k in ("r2c", "c2r")]
        have_wisdom = all(f.exists() for f in files)
        nk = n * n * (n // 2 + 1)
        box = fftw.fftwf_malloc(8 * nk)
        data = np.ctypeslib.as_array((ctypes.c_float * (2 * nk)).from_address(box))
        np.random.default_rng(1).random(out=data, dtype=np.float32)
        times = {"estimate": [], "wisdom": []}
        try:
            for mode in ("estimate", "wisdom", "estimate", "wisdom"):
                fftw.fftwf_forget_wisdom()  # FFTW also uses wisdom in memory for ESTIMATE plans
                if mode == "wisdom":
                    if not have_wisdom:
                        continue
                    for f in files:
                        if fftw.fftwf_import_wisdom_from_filename(str(f).encode()) != 1:
                            raise OSError(f"could not import {f}")
                flag = FFTW_ESTIMATE if mode == "estimate" else FFTW_WISDOM_ONLY
                for _ in range(args.repeat):
                    t = one_fft("r2c", n, box, flag) + one_fft("c2r", n, box, flag)
                    times[mode].append(t)
                    data *= np.float32(1.0 / n**3)  # undo c2r's scaling (not timed)
                print(f"  n={n:5d} {mode:8s} pairs: " + " ".join(f"{t:8.3f}s" for t in times[mode][-args.repeat:]),
                      flush=True)
        except LookupError as e:
            print(f"  n={n}: {e}", flush=True)
        finally:
            fftw.fftwf_free(box)
        e = statistics.median(times["estimate"])
        w = statistics.median(times["wisdom"]) if times["wisdom"] else float("nan")
        rows.append((n, e, w, "" if have_wisdom else "no wisdom files"))
    print(f"\n{'n':>5} {'ESTIMATE r2c+c2r':>17} {'wisdom r2c+c2r':>15} {'wisdom/ESTIMATE':>16}")
    for n, e, w, note in rows:
        print(f"{n:5d} {e:16.3f}s {w:14.3f}s {w / e:16.3f}  {note}")


if __name__ == "__main__":
    main()
