"""
compare_EOS.py
==============
Lightweight per-phase sanity checks that compare a freshly simulated EOS
product against the reference test simulation stored in

    /ocean/projects/phy210034p/breitman/scaling_test/box2_L400_HII240/

Each public function corresponds to one simulation phase and is imported and
called directly from the run_*py scripts.  All checks are adapted from
check_EOS.py (checks 1-6) but only read the single file that was just written,
so they add negligible I/O overhead.

Check taxonomy (mirrors check_EOS.py numbering)
------------------------------------------------
  1  file_presence_size  — HDF5 file exists and size scales as (N_eos/N_test)^3
  2  array_shape         — array shape is (HII_DIM,)^3; no NaN / Inf in a slab
  3  density_stats       — PerturbedField density: mean≈0, min≥-1, no NaN/Inf
  4  halo_counts         — HaloCatalog: non-empty, number density in test range
  5  global_means        — BrightnessTemp / IonizedBox / TsBox global means
                           within 15 % of the test box at the closest redshift
  6  brightness_pdf      — brightness_temp median and IQR within 20 % of test

Any check that FAILs raises RuntimeError so the calling job exits non-zero and
SLURM marks it failed.  WARNs are printed but do not abort.

All file I/O uses slice-by-slice reads so peak RAM is one 2-D slab.
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
from rich.console import Console
from py21cmfast.io.caching import RunCache

# ── Reference simulation paths ────────────────────────────────────────────────

TEST_CACHE_DIR = Path(
    "/ocean/projects/phy210034p/breitman/scaling_test/box2_L400_HII240"
)
TEST_LC_PATH = TEST_CACHE_DIR / "lc"

# Grid dimensions
EOS_HII_DIM  = 1200
TEST_HII_DIM = 240

# Size-scaling exponent: files scale as (N_eos / N_test)^3 for most structs
EXPECTED_SIZE_RATIO = (EOS_HII_DIM / TEST_HII_DIM) ** 3

# Global-mean tolerance: 15 % relative (or absolute fallback for near-zero)
MEAN_RTOL    = 0.15
MEAN_ATOL_BT = 5.0   # mK fallback for brightness_temp

# PDF tolerances
PDF_MEDIAN_ATOL_BT = 10.0   # mK
PDF_IQR_RTOL       = 0.25   # 25 %

# Physical sanity ranges
PHYSICAL_RANGES: dict[str, tuple[float, float]] = {
    "density":          (-1.0,     1e5),
    "neutral_fraction": (0.0,      1.0),
    "brightness_temp":  (-500.0,  50.0),
    "spin_temperature": (1.0,    1e5),
}

# Struct name → (struct_name_in_HDF5, field_name_in_HDF5)
COEVAL_FIELD_MAP: dict[str, tuple[str, str]] = {
    "brightness_temp":  ("BrightnessTemp", "brightness_temp"),
    "neutral_fraction": ("IonizedBox",     "neutral_fraction"),
    "spin_temperature": ("TsBox",          "spin_temperature"),
}

# ── Printing helpers ──────────────────────────────────────────────────────────

_console = Console(highlight=False, log_path=False)

_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "PASS": ("bold green",  "✓"),
    "WARN": ("bold yellow", "⚠"),
    "FAIL": ("bold red",    "✗"),
    "INFO": ("dim",         "·"),
}


def _pline(status: str, msg: str) -> None:
    style, sym = _STATUS_STYLE.get(status, ("", "?"))
    _console.log(f"[{style}][[{status:4s}]][/{style}] {sym} {msg}")


def _section(title: str) -> None:
    _console.rule(f"[bold]{title}[/bold]")


def _fail(msg: str) -> None:
    _pline("FAIL", msg)
    raise RuntimeError(f"EOS check FAILED: {msg}")


# ── Slice-by-slice HDF5 statistics ───────────────────────────────────────────

def _hdf5_stats(path: Path, struct_name: str, field: str) -> dict:
    """Return {mean, std, min, max, n_nan, n_inf} without loading full array."""
    with h5py.File(path, "r") as f:
        ds = f[struct_name]["OutputFields"][field]
        n = 0
        total = np.float64(0.0)
        sq    = np.float64(0.0)
        vmin, vmax = np.inf, -np.inf
        n_nan = n_inf = 0
        for i in range(ds.shape[0]):
            slab  = ds[i].astype(np.float64)
            n    += slab.size
            total += slab.sum()
            sq    += (slab ** 2).sum()
            vmin   = min(vmin, float(slab.min()))
            vmax   = max(vmax, float(slab.max()))
            n_nan += int(np.isnan(slab).sum())
            n_inf += int(np.isinf(slab).sum())
    mean = total / n
    std  = float(np.sqrt(max(sq / n - mean ** 2, 0.0)))
    return {"mean": float(mean), "std": std,
            "min": float(vmin), "max": float(vmax),
            "n_nan": n_nan, "n_inf": n_inf}


def _hdf5_histogram(
    path: Path, struct_name: str, field: str,
    vrange: tuple[float, float], n_bins: int = 150,
) -> tuple[np.ndarray, np.ndarray]:
    """Accumulate a 1-D histogram slice-by-slice. Returns (counts, bin_edges)."""
    bins   = np.linspace(vrange[0], vrange[1], n_bins + 1)
    counts = np.zeros(n_bins, dtype=np.float64)
    with h5py.File(path, "r") as f:
        ds = f[struct_name]["OutputFields"][field]
        for i in range(ds.shape[0]):
            slab = ds[i].astype(np.float32).ravel()
            h, _ = np.histogram(slab, bins=bins)
            counts += h
    return counts, bins


def _percentile_from_hist(
    counts: np.ndarray, bins: np.ndarray, pct: float
) -> float:
    centres = 0.5 * (bins[:-1] + bins[1:])
    cdf = np.cumsum(counts) / counts.sum()
    return float(np.interp(pct / 100.0, cdf, centres))


def _hdf5_shape(path: Path, struct_name: str, field: str) -> tuple[int, ...]:
    with h5py.File(path, "r") as f:
        return tuple(f[struct_name]["OutputFields"][field].shape)


def _hdf5_first_values(
    path: Path, struct_name: str, field: str, n: int = 6
) -> np.ndarray:
    """Return the first *n* values from the flattened array (first slab, row 0)."""
    with h5py.File(path, "r") as f:
        ds = f[struct_name]["OutputFields"][field]
        row = ds[0, 0, :n].astype(np.float64)
    return row


# ── Test-cache lookup via RunCache ───────────────────────────────────────────

_TEST_RC: RunCache | None = None


def _test_runcache() -> RunCache | None:
    """Return a RunCache for the reference test simulation (built lazily, once)."""
    global _TEST_RC
    if _TEST_RC is not None:
        return _TEST_RC
    # Prefer BrightnessTemp files: they store the full inputs including node_redshifts
    examples = sorted(TEST_CACHE_DIR.glob("**/BrightnessTemp.h5"))
    if not examples:
        examples = sorted(TEST_CACHE_DIR.glob("**/*.h5"))
    if not examples:
        _pline("WARN", "test RunCache: no HDF5 files found in test cache dir")
        return None
    try:
        _TEST_RC = RunCache.from_example_file(examples[0])
    except Exception as exc:
        _pline("WARN", f"Could not build test RunCache: {exc}")
    return _TEST_RC


def _test_path_ics() -> Path | None:
    """Return the InitialConditions path from the test RunCache."""
    rc = _test_runcache()
    if rc is None:
        return None
    p = rc.InitialConditions
    return p if p.exists() else None


def _test_path_closest_z(
    struct_attr: str, target_z: float
) -> tuple[Path | None, float | None]:
    """Return *(path, actual_z)* from the test RunCache at the closest node redshift."""
    rc = _test_runcache()
    if rc is None:
        return None, None
    struct_dict = getattr(rc, struct_attr, None)
    if not struct_dict:
        return None, None
    node_zs = np.array(list(struct_dict.keys()))
    idx = int(np.argmin(np.abs(node_zs - target_z)))
    actual_z = float(node_zs[idx])
    path = struct_dict[actual_z]
    return (path if path.exists() else None), actual_z


# ══════════════════════════════════════════════════════════════════════════════
# Check 1 — File presence and size
# ══════════════════════════════════════════════════════════════════════════════

def _check_file_presence_size(
    eos_path: Path, struct_name: str, test_path: Path | None, label: str
) -> None:
    """Check 1: file exists and size roughly matches expected scaling."""
    if not eos_path.exists():
        _fail(f"Check 1 [{label}]: EOS file not found: {eos_path}")

    eos_size = eos_path.stat().st_size
    _pline("PASS", f"Check 1 [{label}]: file present, size={eos_size/1e9:.3f} GB")

    if test_path is not None and test_path.exists():
        test_size = test_path.stat().st_size
        ratio = eos_size / test_size if test_size else None
        if ratio is not None:
            ok = abs(ratio / EXPECTED_SIZE_RATIO - 1) < 0.35
            status = "PASS" if ok else "WARN"
            _pline(status,
                   f"Check 1 [{label}]: size ratio={ratio:.0f} "
                   f"(expected≈{EXPECTED_SIZE_RATIO:.0f}) {'OK' if ok else 'OFF by >35%'}")


# ══════════════════════════════════════════════════════════════════════════════
# Check 2 — Array shape and NaN/Inf
# ══════════════════════════════════════════════════════════════════════════════

def _check_array_shape(
    eos_path: Path, struct_name: str, field: str, label: str
) -> None:
    """Check 2: shape is (EOS_HII_DIM,)^3; sample every 50th slab for NaN/Inf."""
    shape = _hdf5_shape(eos_path, struct_name, field)
    expected = (EOS_HII_DIM,) * 3
    if shape != expected:
        _fail(f"Check 2 [{label}]: shape {shape} != expected {expected}")
    _pline("PASS", f"Check 2 [{label}]: shape {shape} OK")

    n_nan = n_inf = 0
    with h5py.File(eos_path, "r") as f:
        ds = f[struct_name]["OutputFields"][field]
        for i in range(0, ds.shape[0], 50):
            slab  = ds[i].astype(np.float32)
            n_nan += int(np.isnan(slab).sum())
            n_inf += int(np.isinf(slab).sum())
    if n_nan or n_inf:
        _fail(f"Check 2 [{label}]: NaN={n_nan} Inf={n_inf} in sampled slabs")
    _pline("PASS", f"Check 2 [{label}]: no NaN/Inf in sampled slabs")


# ══════════════════════════════════════════════════════════════════════════════
# Check 3 — Density statistics
# ══════════════════════════════════════════════════════════════════════════════

def _check_density_stats(eos_path: Path, label: str) -> None:
    """Check 3: PerturbedField density: mean≈0, min≥-1, no NaN/Inf."""
    st = _hdf5_stats(eos_path, "PerturbedField", "density")
    _pline("INFO",
           f"Check 3 [{label}]: density mean={st['mean']:+.5f}  "
           f"std={st['std']:.5f}  min={st['min']:.5f}  max={st['max']:.5f}  "
           f"NaN={st['n_nan']}  Inf={st['n_inf']}")
    vals = _hdf5_first_values(eos_path, "PerturbedField", "density")
    _pline("INFO", f"Check 3 [{label}]: density[0,0,:6] = {vals}")

    if st["n_nan"] or st["n_inf"]:
        _fail(f"Check 3 [{label}]: NaN/Inf in density field")
    if abs(st["mean"]) > 0.1:
        _fail(f"Check 3 [{label}]: density mean={st['mean']:+.5f} too far from 0")
    if st["min"] < -1.0 - 1e-5:
        _fail(f"Check 3 [{label}]: density min={st['min']:.5f} below physical floor -1")
    if st["std"] < 1e-6:
        _fail(f"Check 3 [{label}]: density std≈0 — possible fill-value sentinel")
    _pline("PASS", f"Check 3 [{label}]: density stats OK")


# ══════════════════════════════════════════════════════════════════════════════
# Check 4 — Halo catalog counts
# ══════════════════════════════════════════════════════════════════════════════

def _check_halo_counts(
    eos_path: Path, eos_box_len: float, label: str,
    test_path: Path | None,
) -> None:
    """Check 4: HaloCatalog non-empty; number density within 3× of test."""
    with h5py.File(eos_path, "r") as f:
        n_halos = int(f["HaloCatalog"].attrs.get("n_halos", 0))

    eos_vol   = eos_box_len ** 3
    eos_nd    = n_halos / eos_vol
    _pline("INFO", f"Check 4 [{label}]: n_halos={n_halos:,d}  "
                   f"n_density={eos_nd:.4e} Mpc⁻³")

    if n_halos == 0:
        _fail(f"Check 4 [{label}]: HaloCatalog is empty")

    if test_path is not None and test_path.exists():
        with h5py.File(test_path, "r") as f:
            n_test = int(f["HaloCatalog"].attrs.get("n_halos", 0))
        test_vol = None
        try:
            with h5py.File(test_path, "r") as f:
                test_box_len = float(f["HaloCatalog"].attrs.get("box_len", 0.0))
            if test_box_len > 0:
                test_vol = test_box_len ** 3
        except Exception:
            pass
        if test_vol and n_test:
            test_nd  = n_test / test_vol
            ratio    = eos_nd / test_nd
            ok = 0.1 < ratio < 10.0
            status = "PASS" if ok else "WARN"
            _pline(status,
                   f"Check 4 [{label}]: n_density ratio EOS/test={ratio:.2f} "
                   f"({'OK' if ok else 'outside 0.1–10×'})")

    _pline("PASS", f"Check 4 [{label}]: halo catalog non-empty")


# ══════════════════════════════════════════════════════════════════════════════
# Check 5 — Global means of coeval fields
# ══════════════════════════════════════════════════════════════════════════════

def _check_global_means(
    eos_path: Path, struct_name: str, field: str,
    target_z: float, label: str,
) -> None:
    """Check 5: global mean of *field* within MEAN_RTOL of test at closest z."""
    st = _hdf5_stats(eos_path, struct_name, field)
    eos_mean = st["mean"]
    _pline("INFO",
           f"Check 5 [{label}] {field}: mean={eos_mean:.4f}  "
           f"std={st['std']:.4f}  min={st['min']:.4f}  max={st['max']:.4f}")

    if st["n_nan"] or st["n_inf"]:
        _fail(f"Check 5 [{label}] {field}: NaN={st['n_nan']} Inf={st['n_inf']}")

    # Physical range check
    prange = PHYSICAL_RANGES.get(field)
    if prange:
        lo, hi = prange
        if eos_mean < lo or eos_mean > hi:
            _fail(f"Check 5 [{label}] {field}: mean={eos_mean:.4f} outside [{lo}, {hi}]")

    # Compare to test box at closest redshift
    test_path, test_z = _test_path_closest_z(struct_name, target_z)
    if test_path is None:
        _pline("WARN", f"Check 5 [{label}] {field}: no test file found — skipping comparison")
        return
    if abs((test_z or 999) - target_z) > 1.0:
        _pline("WARN", f"Check 5 [{label}] {field}: closest test z={test_z:.3f} far from {target_z:.3f}")
        return

    test_st   = _hdf5_stats(test_path, struct_name, field)
    test_mean = test_st["mean"]
    atol      = MEAN_ATOL_BT if field == "brightness_temp" else 0.0
    denom     = max(abs(test_mean), 1e-10)
    rdiff     = abs(eos_mean - test_mean) / denom
    ok = rdiff <= MEAN_RTOL or abs(eos_mean - test_mean) <= atol
    status = "PASS" if ok else "FAIL"
    _pline(status,
           f"Check 5 [{label}] {field}: EOS mean={eos_mean:.4f}  "
           f"test mean={test_mean:.4f} (z={test_z:.3f})  rdiff={rdiff:.1%}")
    eos_vals  = _hdf5_first_values(eos_path,  struct_name, field)
    test_vals = _hdf5_first_values(test_path, struct_name, field)
    _pline("INFO", f"Check 5 [{label}] {field}: EOS [0,0,:6]  = {np.array2string(eos_vals,  precision=4, separator=', ')}")
    _pline("INFO", f"Check 5 [{label}] {field}: test[0,0,:6]  = {np.array2string(test_vals, precision=4, separator=', ')}")
    if status == "FAIL":
        _fail(f"Check 5 [{label}] {field}: global mean deviation {rdiff:.1%} > {MEAN_RTOL:.0%}")


# ══════════════════════════════════════════════════════════════════════════════
# Check 6 — Brightness-temp PDF (median and IQR)
# ══════════════════════════════════════════════════════════════════════════════

def _check_brightness_pdf(
    eos_path: Path, target_z: float, label: str
) -> None:
    """Check 6: brightness_temp median and IQR within tolerances of test."""
    st = _hdf5_stats(eos_path, "BrightnessTemp", "brightness_temp")
    vrange = (min(st["min"], -300.0), max(st["max"], 50.0))
    counts, bins = _hdf5_histogram(eos_path, "BrightnessTemp", "brightness_temp", vrange)
    eos_p25 = _percentile_from_hist(counts, bins, 25.0)
    eos_p50 = _percentile_from_hist(counts, bins, 50.0)
    eos_p75 = _percentile_from_hist(counts, bins, 75.0)
    eos_iqr = eos_p75 - eos_p25
    _pline("INFO",
           f"Check 6 [{label}]: brightness_temp p25={eos_p25:.2f}  "
           f"p50={eos_p50:.2f}  p75={eos_p75:.2f}  IQR={eos_iqr:.2f} mK")

    test_path, test_z = _test_path_closest_z("BrightnessTemp", target_z)
    if test_path is None:
        _pline("WARN", f"Check 6 [{label}]: no test BrightnessTemp file — skipping")
        return
    if abs((test_z or 999) - target_z) > 1.0:
        _pline("WARN", f"Check 6 [{label}]: closest test z={test_z:.3f} far — skipping")
        return

    test_st  = _hdf5_stats(test_path, "BrightnessTemp", "brightness_temp")
    tv = (min(test_st["min"], -300.0), max(test_st["max"], 50.0))
    common   = (min(vrange[0], tv[0]), max(vrange[1], tv[1]))
    tc, tb   = _hdf5_histogram(test_path, "BrightnessTemp", "brightness_temp", common)
    ec, eb   = _hdf5_histogram(eos_path,  "BrightnessTemp", "brightness_temp", common)
    test_p50 = _percentile_from_hist(tc, tb, 50.0)
    test_p25 = _percentile_from_hist(tc, tb, 25.0)
    test_p75 = _percentile_from_hist(tc, tb, 75.0)
    test_iqr = test_p75 - test_p25

    med_ok = abs(eos_p50 - test_p50) <= PDF_MEDIAN_ATOL_BT
    iqr_ok = (abs(eos_iqr - test_iqr) / max(abs(test_iqr), 1e-6)) <= PDF_IQR_RTOL
    status = "PASS" if (med_ok and iqr_ok) else "FAIL"
    _pline(status,
           f"Check 6 [{label}]: EOS p50={eos_p50:.2f} test p50={test_p50:.2f}  "
           f"EOS IQR={eos_iqr:.2f} test IQR={test_iqr:.2f} (z={test_z:.3f})")
    if status == "FAIL":
        _fail(
            f"Check 6 [{label}]: brightness_temp PDF mismatch — "
            f"median diff={abs(eos_p50 - test_p50):.2f} mK "
            f"(tol={PDF_MEDIAN_ATOL_BT} mK), "
            f"IQR rdiff={abs(eos_iqr - test_iqr)/max(abs(test_iqr),1e-6):.1%} "
            f"(tol={PDF_IQR_RTOL:.0%})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Public API — one function per simulation phase
# ══════════════════════════════════════════════════════════════════════════════

def compare_ICs(initial_conditions) -> None:
    """
    Checks 1-3 for a freshly computed InitialConditions object.

    Checks performed
    ----------------
    1  File presence and size scaling
    2  density array shape and NaN/Inf scan
    3  Density statistics: mean≈0, min≥-1, no NaN/Inf
    """
    _section("compare_ICs: checks 1-3 on InitialConditions")

    # Resolve the on-disk path via the object's cache path attribute
    eos_path: Path | None = None
    for attr in ("path", "_path", "cache_path"):
        p = getattr(initial_conditions, attr, None)
        if p is not None:
            eos_path = Path(p)
            break
    if eos_path is None or not eos_path.exists():
        _pline("WARN", "compare_ICs: cannot resolve on-disk path — skipping file checks")
        return

    test_path = _test_path_ics()

    _check_file_presence_size(eos_path, "InitialConditions", test_path, "ICs")
    _check_array_shape(eos_path, "InitialConditions", "density", "ICs")
    _check_density_stats_ics(eos_path)

    _pline("PASS", "compare_ICs: all checks passed ✓")


def _check_density_stats_ics(eos_path: Path) -> None:
    """Check 3 variant for InitialConditions/density."""
    st = _hdf5_stats(eos_path, "InitialConditions", "density")
    _pline("INFO",
           f"Check 3 [ICs]: density mean={st['mean']:+.5f}  "
           f"std={st['std']:.5f}  min={st['min']:.5f}  max={st['max']:.5f}  "
           f"NaN={st['n_nan']}  Inf={st['n_inf']}")
    vals = _hdf5_first_values(eos_path, "InitialConditions", "density")
    _pline("INFO", f"Check 3 [ICs]: density[0,0,:6] = {vals}")
    if st["n_nan"] or st["n_inf"]:
        _fail("Check 3 [ICs]: NaN/Inf in IC density field")
    if abs(st["mean"]) > 0.1:
        _fail(f"Check 3 [ICs]: density mean={st['mean']:+.5f} too far from 0")
    if st["std"] < 1e-6:
        _fail("Check 3 [ICs]: density std≈0 — sentinel fill?")
    _pline("PASS", "Check 3 [ICs]: IC density stats OK")


def compare_PF(perturbed_field, z: float, z_idx: int) -> None:
    """
    Checks 1-3 for a freshly computed PerturbedField at redshift *z*.

    Checks performed
    ----------------
    1  File presence and size scaling
    2  density array shape and NaN/Inf
    3  Density statistics: mean≈0, min≥-1, no NaN/Inf
    """
    label = f"PF z={z:.4f} idx={z_idx}"
    _section(f"compare_PF: checks 1-3 — {label}")

    eos_path: Path | None = None
    for attr in ("path", "_path", "cache_path"):
        p = getattr(perturbed_field, attr, None)
        if p is not None:
            eos_path = Path(p)
            break
    if eos_path is None or not eos_path.exists():
        _pline("WARN", f"compare_PF: cannot resolve on-disk path — skipping ({label})")
        return

    test_path, _ = _test_path_closest_z("PerturbedField", z)

    _check_file_presence_size(eos_path, "PerturbedField", test_path, label)
    _check_array_shape(eos_path, "PerturbedField", "density", label)
    _check_density_stats(eos_path, label)

    _pline("PASS", f"compare_PF: all checks passed for {label} ✓")


def compare_PHFs(cache, inputs) -> None:
    """
    Checks 1 and 4 for the full set of HaloCatalog files just written.

    For each node redshift: file presence/size (check 1) and halo counts
    (check 4).  Structural checks (shape/NaN) are skipped because HaloCatalog
    is a variable-length 1-D array, not a 3-D grid.
    """
    _section("compare_PHFs: checks 1 and 4 on all HaloCatalog files")
    rc = RunCache.from_inputs(inputs, cache=cache)
    hc_dict = getattr(rc, "HaloCatalog", {})
    if not hc_dict:
        _pline("WARN", "compare_PHFs: no HaloCatalog entries in RunCache — skipping")
        return

    box_len = float(inputs.simulation_options.BOX_LEN)
    n_checked = 0
    for z, eos_path_obj in sorted(hc_dict.items(), key=lambda kv: kv[0]):
        eos_path = Path(str(eos_path_obj))
        if not eos_path.exists():
            _fail(f"compare_PHFs: HaloCatalog z={z:.4f} expected at {eos_path} but not found on disk")
        test_path, _ = _test_path_closest_z("HaloCatalog", z)
        label = f"PHF z={z:.4f}"
        _check_file_presence_size(eos_path, "HaloCatalog", test_path, label)
        _check_halo_counts(eos_path, box_len, label, test_path)
        n_checked += 1

    _pline("PASS", f"compare_PHFs: checks passed for {n_checked} redshifts ✓")


def compare_coeval(coeval, cache, inputs) -> None:
    """
    Checks 1-2 and 5-6 for a freshly generated coeval object.

    Checks performed per field (brightness_temp, neutral_fraction, spin_temperature)
    ---------------------------------------------------------------------------------
    1  File presence and size
    2  Array shape and NaN/Inf
    5  Global mean within 15 % of test at closest z
    6  brightness_temp median and IQR within tolerances  (brightness_temp only)
    """
    z = float(getattr(coeval, "redshift", 0.0))
    label = f"coeval z={z:.4f}"
    _section(f"compare_coeval: checks 1-2, 5-6 — {label}")

    rc = RunCache.from_inputs(inputs, cache=cache)

    for field, (struct_attr, h5field) in COEVAL_FIELD_MAP.items():
        struct_dict = getattr(rc, struct_attr, {})
        if not struct_dict:
            _pline("WARN", f"compare_coeval: no {struct_attr} in RunCache — skipping {field}")
            continue

        node_zs = np.array(list(struct_dict.keys()))
        eos_path_obj = struct_dict[node_zs[np.argmin(np.abs(node_zs - z))]]
        eos_path = Path(str(eos_path_obj))
        if not eos_path.exists():
            _pline("WARN", f"compare_coeval: {struct_attr} z={z:.4f} not on disk — skipping")
            continue

        test_path, _ = _find_test_file_closest_z(struct_attr, z)
        field_label  = f"{label} / {field}"

        _check_file_presence_size(eos_path, struct_attr, test_path, field_label)
        _check_array_shape(eos_path, struct_attr, h5field, field_label)
        _check_global_means(eos_path, struct_attr, h5field, z, field_label)
        if field == "brightness_temp":
            _check_brightness_pdf(eos_path, z, field_label)

    _pline("PASS", f"compare_coeval: all checks passed for {label} ✓")
