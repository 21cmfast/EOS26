"""Shared, dependency-free helpers for the EOS26 scaling harness.

Only the standard library is used here so that the driver (``measure.py``) and
``summarize.py`` never import numpy/py21cmfast: the driver process must stay
tiny, and the summary must work on a login node / laptop without 21cmFAST.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Phase order matters: each phase consumes the products of the previous ones,
# exactly as in production (ICs -> PFs -> PHFs -> coevals, one job each).
PHASES: tuple[str, ...] = ("ics", "pf", "phf", "coeval")

SCALING_DIR = Path(__file__).resolve().parent
EOS26_ROOT = SCALING_DIR.parent

# Bump when the *meaning* of the recorded numbers changes (not for cosmetic
# edits). Stored in every result so old and new measurements are never mixed
# silently.
SCHEMA_VERSION = 1


def utc_now() -> str:
    """ISO-8601 UTC timestamp with seconds precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def config_name(hii_dim: int, n_threads: int, coeval_batch: int = 0) -> str:
    """Directory name of one configuration.

    ``_CBxx`` is appended when coevals are measured in production-like batches
    of xx redshifts per process (0 = the full evolution in one process).
    """
    name = f"HII_DIM_{hii_dim:04d}_NT_{n_threads:02d}"
    return f"{name}_CB{coeval_batch:02d}" if coeval_batch > 0 else name


def parse_config_name(name: str) -> tuple[int, int, int] | None:
    """Inverse of :func:`config_name`: (HII_DIM, N_THREADS, coeval_batch)."""
    import re

    m = re.fullmatch(r"HII_DIM_(\d+)_NT_(\d+)(?:_CB(\d+))?", name)
    return (int(m[1]), int(m[2]), int(m[3] or 0)) if m else None


def parse_phases(text: str) -> tuple[str, ...]:
    """Parse ``ics,pf`` / ``ics+pf`` / ``ics pf`` / ``all`` into ordered phases."""
    raw = text.replace("+", ",").replace(" ", ",").split(",")
    names = [p.strip().lower() for p in raw if p.strip()]
    if not names or names == ["all"]:
        return PHASES
    unknown = sorted(set(names) - set(PHASES))
    if unknown:
        raise ValueError(f"unknown phase(s) {unknown}; valid: {', '.join(PHASES)} or 'all'")
    return tuple(p for p in PHASES if p in names)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    with path.open() as fh:
        return json.load(fh)


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write JSON so that readers never see a partial file.

    The temporary name is unique per host+pid, so two writers can never
    clobber each other's temporary file (the old harness used one shared
    ``.tmp`` name, which is how several v4.2 result files got corrupted).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{socket.gethostname()}.{os.getpid()}.tmp")
    with tmp.open("w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def append_jsonl(path: Path, record: dict) -> None:
    """Append one JSON record per line (used for per-step progress)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True, default=str) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def fmt_bytes(n: float | None) -> str:
    if n is None:
        return "n/a"
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(n) < 1024 or unit == "TiB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.2f} TiB"


def fmt_seconds(s: float | None) -> str:
    if s is None:
        return "n/a"
    s = float(s)
    if s < 120:
        return f"{s:.1f}s"
    if s < 7200:
        return f"{s / 60:.1f}m"
    return f"{s / 3600:.2f}h"


def pbs_jobid() -> str | None:
    return os.environ.get("PBS_JOBID")


def host_info() -> dict[str, Any]:
    """Small, cheap description of where we are running."""
    info: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "pbs_jobid": pbs_jobid(),
        "pbs_queue": os.environ.get("PBS_QUEUE"),
        "pbs_ncpus": os.environ.get("PBS_NCPUS"),
        "cpu_count": os.cpu_count(),
    }
    if hasattr(os, "sched_getaffinity"):
        info["cpus_allowed"] = len(os.sched_getaffinity(0))
    try:  # total physical memory (Linux / macOS)
        info["mem_total_bytes"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        pass
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    info["cpu_model"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    for key in ("OMP_NUM_THREADS", "OMP_DYNAMIC", "OMP_PROC_BIND", "OMP_PLACES"):
        info[key] = os.environ.get(key)
    return info


class Timer:
    """Wall + process-CPU timer (process CPU time includes all OpenMP threads)."""

    def __enter__(self) -> "Timer":
        self.wall0 = time.perf_counter()
        self.cpu0 = time.process_time()
        return self

    def __exit__(self, *_: object) -> None:
        self.wall = time.perf_counter() - self.wall0
        self.cpu = time.process_time() - self.cpu0

    @property
    def cores(self) -> float:
        return self.cpu / self.wall if self.wall > 0 else 0.0
