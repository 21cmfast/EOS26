"""Peak-memory measurement for the scaling worker.

Primary method (Linux): the kernel's own resident-set high-water mark
(``VmHWM`` in /proc/self/status). It is exact -- no sampling interval can miss
a short-lived spike -- and covers everything in the process (Python, numpy,
21cmFAST's C/OpenMP allocations, FFTW plans, all threads). Writing ``5`` to
/proc/self/clear_refs resets the mark to the current RSS (Linux >= 4.0), so we
can get the exact peak of *each step* (each PF, each coeval redshift), not just
of the whole process.

Fallback (macOS / restricted kernels): a background sampler thread plus
``getrusage`` maxrss. This can underestimate short spikes; the method used is
recorded next to every number so it is never ambiguous.

A background sampler always runs as well, at a coarse interval, to write an
RSS time series (CSV) for diagnostics/plots and as a cross-check.

The sampler also reads the memory *cgroup* of the job when it can (cgroup v1
or v2). That is what PBS accounts and enforces: it includes page cache (e.g.
HDF5 file I/O) on top of RSS. The page cache is mostly reclaimable, but at
HII_DIM=1500 PBS reported ~0.45 TB more "Memory Used" than the process RSS, so
the ratio of the two is worth knowing when choosing a safety margin.
"""

from __future__ import annotations

import os
import resource
import sys
import threading
import time
from pathlib import Path

_STATUS = "/proc/self/status"
_CLEAR_REFS = "/proc/self/clear_refs"


def _status_field_bytes(name: str) -> int | None:
    try:
        with open(_STATUS) as fh:
            for line in fh:
                if line.startswith(name + ":"):
                    return int(line.split()[1]) * 1024  # kB -> bytes
    except OSError:
        return None
    return None


def current_rss() -> int:
    """Current resident set size in bytes."""
    rss = _status_field_bytes("VmRSS")
    if rss is not None:
        return rss
    try:
        import psutil  # optional; only needed off Linux

        return int(psutil.Process().memory_info().rss)
    except Exception:  # pragma: no cover - last resort
        ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(ru if sys.platform == "darwin" else ru * 1024)


def _ru_maxrss_bytes() -> int:
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(ru if sys.platform == "darwin" else ru * 1024)  # macOS: bytes, Linux: kB


class CgroupMemory:
    """Best-effort reader of this process's memory cgroup (what PBS enforces)."""

    _V1_STAT = ("total_rss", "total_cache", "total_mapped_file", "total_dirty", "total_writeback", "total_shmem")
    _V2_STAT = ("anon", "file", "file_mapped", "file_dirty", "file_writeback", "shmem")

    def __init__(self) -> None:
        self.version: int | None = None
        self.dir: Path | None = None
        try:
            lines = Path("/proc/self/cgroup").read_text().splitlines()
        except OSError:
            return
        for line in lines:
            _, ctrls, path = line.split(":", 2)
            d = Path("/sys/fs/cgroup/memory") / path.lstrip("/")
            if "memory" in ctrls.split(",") and (d / "memory.usage_in_bytes").exists():
                self.version, self.dir = 1, d
                return
        for line in lines:
            if line.startswith("0::"):
                d = Path("/sys/fs/cgroup") / line[3:].lstrip("/")
                if (d / "memory.current").exists():
                    self.version, self.dir = 2, d
                    return

    def _read_int(self, name: str) -> int | None:
        if self.dir is None:
            return None
        try:
            text = (self.dir / name).read_text().strip()
        except OSError:
            return None
        return None if text in ("", "max") else int(text)

    def usage(self) -> int | None:
        return self._read_int("memory.usage_in_bytes" if self.version == 1 else "memory.current")

    def snapshot(self) -> dict | None:
        """Usage, limit, cgroup-lifetime max usage and a memory.stat subset."""
        if self.dir is None:
            return None
        v1 = self.version == 1
        out: dict = {
            "version": self.version,
            "path": str(self.dir),
            "usage_bytes": self.usage(),
            "limit_bytes": self._read_int("memory.limit_in_bytes" if v1 else "memory.max"),
            # v1: max since the cgroup (= PBS job) started; v2: needs kernel >= 5.19
            "max_usage_bytes": self._read_int("memory.max_usage_in_bytes" if v1 else "memory.peak"),
        }
        keys = self._V1_STAT if v1 else self._V2_STAT
        try:
            for line in (self.dir / "memory.stat").read_text().splitlines():
                k, _, v = line.partition(" ")
                if k in keys:
                    out[f"stat_{k}"] = int(v)
        except OSError:
            pass
        return out


class PeakTracker:
    """Exact per-interval peak RSS via VmHWM reset, with a sampler fallback."""

    def __init__(self, sampler: "RssSampler") -> None:
        self.sampler = sampler
        self.method = "vmhwm_reset" if self._self_test() else "sampler"

    @staticmethod
    def _reset_hwm() -> bool:
        try:
            with open(_CLEAR_REFS, "w") as fh:
                fh.write("5")
            return True
        except OSError:
            return False

    def _self_test(self) -> bool:
        """Check that the kernel really resets VmHWM (allocate, free, reset)."""
        if _status_field_bytes("VmHWM") is None:
            return False
        block = bytearray(64 * 1024 * 1024)  # touch 64 MiB so it is resident
        for i in range(0, len(block), 4096):
            block[i] = 1
        high = _status_field_bytes("VmHWM") or 0
        del block
        if not self._reset_hwm():
            return False
        after = _status_field_bytes("VmHWM") or high
        return after < high - 32 * 1024 * 1024

    def start_interval(self) -> None:
        """Begin a new measurement interval (resets the high-water mark)."""
        if self.method == "vmhwm_reset":
            self._reset_hwm()
        self.sampler.reset_interval_peak()

    def interval_peak(self) -> int:
        """Peak RSS (bytes) since the last ``start_interval``.

        Always the max of the kernel mark and the sampler: the kernel's RSS
        counters are cached per thread (up to 64 page events), so VmHWM can lag
        a concurrent VmRSS read by a few hundred kB. Taking the max keeps the
        number conservative for memory sizing.
        """
        sampled = max(self.sampler.interval_peak(), current_rss())
        if self.method == "vmhwm_reset":
            return max(int(_status_field_bytes("VmHWM") or 0), sampled)
        return sampled


class RssSampler:
    """Background RSS sampler that writes ``elapsed_s,rss_bytes,step`` rows."""

    def __init__(self, csv_path: Path | None, interval_s: float) -> None:
        self.interval_s = max(float(interval_s), 0.01)
        self.csv_path = Path(csv_path) if csv_path else None
        self.step_label = "init"
        self._t0 = time.perf_counter()
        self._peak = 0
        self._interval_peak = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="rss-sampler", daemon=True)
        self._fh = None
        self.cgroup = CgroupMemory()
        self._cg_peak: int | None = None
        self._cg_interval_peak: int | None = None

    def __enter__(self) -> "RssSampler":
        if self.csv_path:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.csv_path.open("w", buffering=1)
            self._fh.write("elapsed_s,rss_bytes,cgroup_bytes,step\n")
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()
        self._record()
        if self._fh:
            self._fh.close()

    def set_step(self, label: str) -> None:
        self.step_label = label

    def reset_interval_peak(self) -> None:
        with self._lock:
            self._interval_peak = current_rss()
            self._cg_interval_peak = self.cgroup.usage()

    def cgroup_interval_peak(self) -> int | None:
        """Sampled peak of the job's cgroup usage (RSS + page cache) this interval."""
        self._record()
        with self._lock:
            return self._cg_interval_peak

    @property
    def cgroup_peak(self) -> int | None:
        self._record()
        return self._cg_peak

    def interval_peak(self) -> int:
        self._record()
        with self._lock:
            return self._interval_peak

    @property
    def peak(self) -> int:
        self._record()
        return self._peak

    def _record(self) -> None:
        rss = current_rss()
        cg = self.cgroup.usage()
        with self._lock:
            self._peak = max(self._peak, rss)
            self._interval_peak = max(self._interval_peak, rss)
            if cg is not None:
                self._cg_peak = max(self._cg_peak or 0, cg)
                self._cg_interval_peak = max(self._cg_interval_peak or 0, cg)
            fh, label = self._fh, self.step_label
        if fh is not None:
            try:
                fh.write(f"{time.perf_counter() - self._t0:.3f},{rss},{'' if cg is None else cg},{label}\n")
            except ValueError:  # file closed during shutdown
                pass

    def _run(self) -> None:
        while not self._stop.wait(self.interval_s):
            self._record()


def process_max_rss() -> int:
    """Lifetime max RSS of this process from getrusage (informational)."""
    return _ru_maxrss_bytes()


def reset_supported() -> bool:
    return os.path.exists(_CLEAR_REFS)
