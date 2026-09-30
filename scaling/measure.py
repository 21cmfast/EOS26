#!/usr/bin/env python3
"""Measure peak memory (and time) of every EOS26 simulation phase for ONE
configuration: a 21cmFAST version label, HII_DIM and N_THREADS.

    python scaling/measure.py --label v4.2 --hii-dim 200 --n-threads 16

Phases (ics -> pf -> phf -> coeval) are measured in order, each in a fresh
subprocess (``_worker.py``), mirroring production where each phase is its own
job. See ``scaling/README.md`` for the full description.

Resuming
    Re-running the same command resumes at the *beginning* of the first phase
    that is not complete: that phase (and everything downstream) is wiped from
    the simulation cache and measured again from scratch. Completed phases are
    never re-measured. If an upstream product needed by the next phase has
    disappeared (e.g. scratch purge), measurement restarts from that phase.

Clean-up
    When all four phases are complete, the simulation cache is deleted
    (``--keep-sim`` disables this). An incomplete configuration always keeps
    its cache so it can be resumed.

Safety
    * one run per configuration at a time (lock file; stale locks from dead
      PBS jobs / processes are detected);
    * a resumed run must use identical inputs, 21cmFAST version and
      ``sim_steps.py`` -- otherwise it refuses (use ``--restart``);
    * every JSON is written atomically.

This driver only uses the standard library; py21cmfast is imported by the
workers only.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    EOS26_ROOT,
    PHASES,
    SCHEMA_VERSION,
    config_name,
    fmt_bytes,
    fmt_seconds,
    host_info,
    parse_phases,
    read_json,
    sha256_file,
    utc_now,
    write_json_atomic,
)

WORKER = Path(__file__).resolve().parent / "_worker.py"
log = logging.getLogger("scaling.driver")

# Fields that must be identical for a resumed configuration.
FINGERPRINT_KEYS = (
    "label",
    "hii_dim",
    "n_threads",
    "random_seed",
    "inputs_sha256",
    "template_sha256",
    "py21cmfast_version",
    "sim_steps_sha256",
    "halo_catalog_mem_factor",
    "coeval_batch",
)


class LockedError(RuntimeError):
    pass


class Interrupted(RuntimeError):
    pass


# --------------------------------------------------------------------------
# lock
# --------------------------------------------------------------------------
class ConfigLock:
    """Exclusive lock for one configuration directory (O_EXCL lock file)."""

    def __init__(self, config_dir: Path) -> None:
        self.path = config_dir / ".lock"
        self.held = False

    def acquire(self, break_lock: bool = False) -> None:
        for _ in range(3):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                info = read_json(self.path, default={}) or {}
                if break_lock or self._is_stale(info):
                    log.warning("removing stale lock %s (%s)", self.path, info)
                    self.path.unlink(missing_ok=True)
                    continue
                raise LockedError(
                    f"{self.path.parent.name} is locked by {info}. Another run of this configuration "
                    "is active. If you are sure it is not, pass --break-lock."
                ) from None
            with os.fdopen(fd, "w") as fh:
                import json

                json.dump({**host_info(), "started_utc": utc_now()}, fh)
            self.held = True
            return
        raise LockedError(f"could not acquire {self.path}")

    @staticmethod
    def _is_stale(info: dict[str, Any]) -> bool:
        jid = info.get("pbs_jobid")
        if jid:
            if jid == os.environ.get("PBS_JOBID"):
                return True  # same job, e.g. PBS re-queued it after a node failure
            if shutil.which("qstat"):
                # qstat exits non-zero for jobs that are no longer queued/running.
                r = subprocess.run(["qstat", jid], capture_output=True, text=True, check=False)
                return r.returncode != 0
        if info.get("hostname") == socket.gethostname() and info.get("pid"):
            try:
                os.kill(int(info["pid"]), 0)
            except ProcessLookupError:
                return True
            except PermissionError:
                return False
            return False
        return False  # cannot tell -> be safe

    def release(self) -> None:
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------
def new_state() -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "complete": False,
        "sim_deleted": False,
        "phases": {p: {"status": "pending", "attempts": 0} for p in PHASES},
        "history": [],
    }


class Driver:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        name = config_name(args.hii_dim, args.n_threads, args.coeval_batch)
        self.config_dir = (args.results_root / args.label / name).resolve()
        self.sim_root = args.sim_root.resolve()
        self.sim_dir = self.sim_root / args.label / name
        self.state_path = self.config_dir / "state.json"
        self.child: subprocess.Popen | None = None
        self.interrupted = False

    # ---- small utilities -------------------------------------------------
    def save_state(self) -> None:
        self.state["updated_utc"] = utc_now()
        write_json_atomic(self.state_path, self.state)

    def event(self, what: str, **kw: Any) -> None:
        self.state["history"].append({"utc": utc_now(), "event": what, "pbs_jobid": os.environ.get("PBS_JOBID"),
                                      "host": socket.gethostname(), **kw})
        self.save_state()

    def _signal(self, signum: int, _frame: Any) -> None:
        log.error("received signal %d; stopping the running phase (it will be resumed from its start)", signum)
        self.interrupted = True
        if self.child and self.child.poll() is None:
            self.child.send_signal(signal.SIGTERM)

    # ---- worker ------------------------------------------------------------
    def run_worker(self, phase: str, attempt: int, batch_index: int = -1) -> tuple[int, Path]:
        tag = "setup" if phase == "setup" else f"{phase}.attempt{attempt}"
        if batch_index >= 0:
            tag += f".batch{batch_index:02d}"
        out = self.config_dir / ("setup.json" if phase == "setup" else f"phases/{tag}.json")
        logfile = self.config_dir / "logs" / f"{tag}.log"
        logfile.parent.mkdir(parents=True, exist_ok=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.unlink(missing_ok=True)

        env = os.environ.copy()
        n = str(self.args.n_threads)
        if env.get("OMP_NUM_THREADS") not in (None, n):
            log.warning("overriding OMP_NUM_THREADS=%s -> %s", env["OMP_NUM_THREADS"], n)
        env.update(OMP_NUM_THREADS=n, OMP_DYNAMIC="FALSE", PYTHONUNBUFFERED="1", PYTHONFAULTHANDLER="1")
        # Same as pbs_scripts/N_coeval_job.sh; OMP_PROC_BIND=TRUE serialised
        # the old scaling jobs (see scaling_old/results/export_makes_job_serial).
        env.pop("OMP_PROC_BIND", None)
        env.pop("OMP_PLACES", None)

        cmd = [sys.executable, str(WORKER), "--config-dir", str(self.config_dir), "--phase", phase,
               "--attempt", str(attempt), "--out", str(out), "--batch-index", str(batch_index)]
        with logfile.open("a") as fh:
            fh.write(f"# {utc_now()} {' '.join(cmd)}\n")
            fh.flush()
            self.child = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env, cwd=EOS26_ROOT)
            code = self.child.wait()
            self.child = None
        return code, out

    # ---- main flow ---------------------------------------------------------
    def setup(self) -> dict[str, Any]:
        code, out = self.run_worker("setup", 0)
        if code != 0 or not out.exists():
            logfile = self.config_dir / "logs/setup.log"
            tail = logfile.read_text().strip().splitlines()[-1:] if logfile.exists() else []
            raise RuntimeError(f"setup failed (exit {code}): {' '.join(tail)} -- see {logfile}")
        setup = read_json(out)
        version = setup["py21cmfast_version"]
        if self.args.expect_version and not re.search(self.args.expect_version, version):
            raise RuntimeError(
                f"py21cmfast {version} (from {setup['py21cmfast_file']}) does not match "
                f"--expect-version {self.args.expect_version!r} for label {self.args.label}. Wrong venv?"
            )
        fingerprint = {
            "label": self.args.label,
            "hii_dim": self.args.hii_dim,
            "n_threads": self.args.n_threads,
            "random_seed": self.args.seed,
            "coeval_batch": self.args.coeval_batch,
            **{k: setup.get(k) for k in FINGERPRINT_KEYS if k in setup},
        }
        cfg_path = self.config_dir / "config.json"
        cfg = read_json(cfg_path)
        if cfg is None:
            write_json_atomic(cfg_path, {"schema": SCHEMA_VERSION, "created_utc": utc_now(), "fingerprint": fingerprint,
                                         "template": str(self.args.template), "sim_dir": str(self.sim_dir),
                                         "setup": setup})
        else:
            diff = {k: (cfg["fingerprint"].get(k), fingerprint.get(k)) for k in FINGERPRINT_KEYS
                    if cfg["fingerprint"].get(k) != fingerprint.get(k)}
            if diff:
                raise RuntimeError(
                    "this configuration was started with different settings; refusing to mix "
                    f"measurements (recorded -> now): {diff}. Use --restart to discard and start over."
                )
        log.info("py21cmfast %s | %s | BOX_LEN=%.0f Mpc | %d node z | memory method: %s",
                 version, setup.get("py21cmfast_file"), setup["inputs_summary"]["BOX_LEN_Mpc"],
                 setup["inputs_summary"]["n_node_redshifts"], setup["memory_method"])
        if setup["memory_method"] != "vmhwm_reset":
            log.warning("exact kernel peak tracking unavailable here; peaks come from a %.2fs sampler",
                        self.args.sample_interval)
        return setup

    def plan(self, setup: dict[str, Any]) -> list[str]:
        phases = self.state["phases"]
        requested = parse_phases(self.args.phases)
        last = max(PHASES.index(p) for p in requested)

        if self.args.redo_from:
            i = PHASES.index(self.args.redo_from)
            for p in PHASES[i:]:
                if phases[p]["status"] != "pending":
                    phases[p]["status"] = "pending"
            self.state["complete"] = False
            self.event("redo_from", phase=self.args.redo_from)

        for p in PHASES:
            if phases[p]["status"] == "running":
                log.warning("phase %s was interrupted in a previous run (attempt %d); it restarts from its beginning",
                            p, phases[p]["attempts"])
                phases[p]["status"] = "interrupted"

        start = next((i for i, p in enumerate(PHASES[: last + 1]) if phases[p]["status"] != "complete"), None)
        if start is None:
            return []
        # The phase we start from needs the products of all completed upstream phases.
        for j in range(start):
            ps = setup["product_status"][PHASES[j]]
            if not ps["complete"]:
                log.warning("phase %s is marked complete but its products are missing from %s (%d/%d files); "
                            "re-measuring from %s", PHASES[j], self.sim_dir, ps["n_present"], ps["n_expected"], PHASES[j])
                start = j
                break
        todo = list(PHASES[start: last + 1])
        extra = [p for p in todo if p not in requested]
        if extra:
            log.info("also running %s (required upstream of the requested phases)", ",".join(extra))
        return todo

    def run_coeval_batches(self, attempt: int) -> tuple[int, Path]:
        """Coeval phase as consecutive production-like batch processes.

        Returns (exit code, path of the aggregated result). The phase peak is
        the maximum over all batches; wall/CPU times are summed.
        """
        size = self.args.coeval_batch
        n_batches = -(-self.n_node_z // size)
        results = []
        for b in range(n_batches):
            log.info("coeval batch %d/%d (%d redshifts per process)", b + 1, n_batches, size)
            code, out = self.run_worker("coeval", attempt, batch_index=b)
            if code != 0 or self.interrupted or not out.exists():
                return (code if code != 0 else 1), out
            results.append(read_json(out))
            log.info("coeval batch %d/%d: peak RSS %s, wall %s", b + 1, n_batches,
                     fmt_bytes(results[-1]["peak_rss_bytes"]), fmt_seconds(results[-1]["wall_s"]))
        last = results[-1]
        if not last.get("all_coevals_present"):
            log.error("after %d batches not all coeval products exist", n_batches)
            return 4, self.config_dir / "phases" / "missing.json"
        steps = [dict(s, batch=r["batch_index"]) for r in results for s in r["steps"]]
        wall = sum(r["wall_s"] for r in results)
        cpu = sum(r["cpu_s"] for r in results)
        agg = {k: v for k, v in last.items() if k not in ("batch_index", "batch_redshifts", "steps", "rss_csv")}
        agg.update(
            started_utc=results[0]["started_utc"],
            wall_s=wall,
            cpu_s=cpu,
            avg_cores=cpu / wall if wall else 0.0,
            baseline_rss_bytes=results[0]["baseline_rss_bytes"],
            peak_rss_bytes=max(r["peak_rss_bytes"] for r in results),
            sampler_peak_rss_bytes=max(r["sampler_peak_rss_bytes"] for r in results),
            steps=steps,
            n_steps=len(steps),
            peak_step=max(steps, key=lambda s: s["peak_rss_bytes"]),
            rss_csv=[r["rss_csv"] for r in results],
            batches=[{"batch_index": r["batch_index"], "z_first": r["batch_redshifts"][0],
                      "z_last": r["batch_redshifts"][-1], "n_outputs": len(r["batch_redshifts"]),
                      "n_steps": r["n_steps"], "peak_rss_bytes": r["peak_rss_bytes"], "wall_s": r["wall_s"],
                      "started_utc": r["started_utc"], "finished_utc": r["finished_utc"]} for r in results],
        )
        out = self.config_dir / "phases" / f"coeval.attempt{attempt}.json"
        write_json_atomic(out, agg)
        return 0, out

    def run_phase(self, phase: str) -> bool:
        st = self.state["phases"][phase]
        for p in PHASES[PHASES.index(phase) + 1:]:  # downstream products get wiped by the worker
            if self.state["phases"][p]["status"] != "pending":
                self.state["phases"][p]["status"] = "pending"
        st["attempts"] += 1
        attempt = st["attempts"]
        st.update(status="running", started_utc=utc_now(), pbs_jobid=os.environ.get("PBS_JOBID"),
                  host=socket.gethostname())
        st.pop("error", None)
        self.event("phase_start", phase=phase, attempt=attempt)
        log.info("=== phase %s (attempt %d) ===", phase, attempt)

        t0 = time.time()
        if phase == "coeval" and self.args.coeval_batch > 0:
            code, out = self.run_coeval_batches(attempt)
        else:
            code, out = self.run_worker(phase, attempt)
        if self.interrupted:
            st.update(status="interrupted", error=f"interrupted by signal (worker exit {code})")
            self.event("phase_interrupted", phase=phase, attempt=attempt, exit_code=code)
            raise Interrupted(phase)
        if code != 0 or not out.exists():
            why = f"worker exit code {code}"
            if code < 0:
                why += f" (killed by signal {-code}{', likely out of memory' if -code == 9 else ''})"
            st.update(status="failed", error=why, finished_utc=utc_now())
            self.event("phase_failed", phase=phase, attempt=attempt, exit_code=code)
            log.error("phase %s FAILED: %s -- see %s", phase, why, self.config_dir / f"logs/{phase}.attempt{attempt}*.log")
            return False

        result = read_json(out)
        final = self.config_dir / "phases" / f"{phase}.json"
        os.replace(out, final)
        st.update(status="complete", finished_utc=utc_now(), attempt_used=attempt,
                  peak_rss_bytes=result["peak_rss_bytes"], wall_s=result["wall_s"],
                  avg_cores=result["avg_cores"], peak_rss_method=result["peak_rss_method"])
        self.event("phase_complete", phase=phase, attempt=attempt, wall_s=time.time() - t0,
                   peak_rss_bytes=result["peak_rss_bytes"])
        log.info("phase %s complete: peak RSS %s, wall %s, %.2f cores", phase, fmt_bytes(result["peak_rss_bytes"]),
                 fmt_seconds(result["wall_s"]), result["avg_cores"])
        return True

    def write_summary(self) -> None:
        cfg = read_json(self.config_dir / "config.json")
        phases = {}
        for p in PHASES:
            r = read_json(self.config_dir / "phases" / f"{p}.json")
            if r is None:
                continue
            ps = r.get("peak_step") or {}
            phases[p] = {k: r.get(k) for k in ("peak_rss_bytes", "peak_rss_method", "baseline_rss_bytes", "wall_s",
                                                "cpu_s", "avg_cores", "n_steps", "product_bytes_total", "attempt",
                                                "started_utc", "finished_utc")}
            phases[p]["peak_step_redshift"] = ps.get("redshift")
            phases[p]["peak_step_index"] = ps.get("index")
        peaks = {p: v["peak_rss_bytes"] for p, v in phases.items()}
        write_json_atomic(self.config_dir / "summary.json", {
            "schema": SCHEMA_VERSION,
            "label": self.args.label,
            "hii_dim": self.args.hii_dim,
            "n_threads": self.args.n_threads,
            "complete": self.state["complete"],
            "fingerprint": cfg["fingerprint"] if cfg else None,
            "py21cmfast_file": (cfg or {}).get("setup", {}).get("py21cmfast_file"),
            "phases": phases,
            "max_peak_rss_bytes": max(peaks.values(), default=None),
            "max_peak_phase": max(peaks, key=peaks.get) if peaks else None,
            "updated_utc": utc_now(),
        })

    def cleanup_sim(self) -> None:
        if not self.sim_dir.exists():
            self.state["sim_deleted"] = True
            return
        # Refuse to delete anything that is not a configuration directory below sim_root.
        if self.sim_root not in self.sim_dir.parents or self.sim_dir.name != self.config_dir.name:
            raise RuntimeError(f"refusing to delete unexpected path {self.sim_dir}")
        log.info("deleting simulation cache %s", self.sim_dir)
        shutil.rmtree(self.sim_dir)
        self.state["sim_deleted"] = True
        self.event("sim_deleted", path=str(self.sim_dir))

    def restart(self) -> None:
        """Archive previous results of this configuration and delete its cache."""
        stamp = time.strftime("%Y%m%dT%H%M%S")
        archive = self.config_dir / "archive" / stamp
        moved = []
        for entry in self.config_dir.iterdir():
            if entry.name in {".lock", "archive", "run.log", "pbs"}:
                continue
            archive.mkdir(parents=True, exist_ok=True)
            entry.rename(archive / entry.name)
            moved.append(entry.name)
        if moved:
            log.warning("--restart: archived previous results to %s", archive)
        if self.sim_dir.exists():
            log.warning("--restart: deleting simulation cache %s", self.sim_dir)
            shutil.rmtree(self.sim_dir)

    def main(self) -> int:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        setup_driver_logging(self.config_dir / "run.log", self.args.log_level)
        log.info("---- start: %s  label=%s HII_DIM=%d N_THREADS=%d phases=%s host=%s pbs_jobid=%s",
                 utc_now(), self.args.label, self.args.hii_dim, self.args.n_threads, self.args.phases,
                 socket.gethostname(), os.environ.get("PBS_JOBID"))
        lock = ConfigLock(self.config_dir)
        lock.acquire(self.args.break_lock)
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGUSR1, signal.SIGUSR2):
            signal.signal(sig, self._signal)
        try:
            if self.args.restart:
                self.restart()
            self.state = read_json(self.state_path) or new_state()
            write_json_atomic(self.config_dir / "request.json", {
                "label": self.args.label,
                "hii_dim": self.args.hii_dim,
                "n_threads": self.args.n_threads,
                "random_seed": self.args.seed,
                "template": str(self.args.template),
                "sim_dir": str(self.sim_dir),
                "sample_interval_s": self.args.sample_interval,
                "coeval_batch": self.args.coeval_batch,
                "log_level": self.args.log_level,
                "measure_py_sha256": sha256_file(Path(__file__)),
                "worker_py_sha256": sha256_file(WORKER),
                "written_utc": utc_now(),
            })
            self.event("run_start", phases=self.args.phases, keep_sim=self.args.keep_sim)
            setup = self.setup()
            self.n_node_z = int(setup["inputs_summary"]["n_node_redshifts"])

            todo = self.plan(setup)
            if not todo:
                log.info("nothing to do: requested phases already complete")
            for phase in todo:
                if not self.run_phase(phase):
                    self.save_state()
                    return 2

            self.state["complete"] = all(self.state["phases"][p]["status"] == "complete" for p in PHASES)
            self.write_summary()
            if self.state["complete"]:
                if self.args.keep_sim:
                    log.info("all phases complete; keeping simulation cache (--keep-sim): %s", self.sim_dir)
                else:
                    self.cleanup_sim()
                log.info("configuration COMPLETE: max peak RSS %s", fmt_bytes(
                    max(self.state["phases"][p]["peak_rss_bytes"] for p in PHASES)))
            self.event("run_end", complete=self.state["complete"])
            return 0
        except Interrupted:
            self.save_state()
            return 143
        except LockedError:
            raise
        except Exception as exc:
            log.exception("driver error: %s", exc)
            if hasattr(self, "state"):
                self.event("driver_error", error=str(exc))
            return 1
        finally:
            lock.release()


def setup_driver_logging(logfile: Path, level: str) -> None:
    fmt = logging.Formatter("%(asctime)s [driver] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger("scaling")
    root.handlers.clear()
    for h in (logging.FileHandler(logfile), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        root.addHandler(h)
    root.setLevel(level)
    root.propagate = False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", required=True, help="21cmFAST version label, e.g. v4.2 or v4.3 (results subfolder)")
    ap.add_argument("--hii-dim", type=int, required=True)
    ap.add_argument("--n-threads", type=int, required=True)
    ap.add_argument("--template", type=Path, default=Path("EOS26.toml"),
                    help="parameter template (relative paths are relative to the EOS26 root)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--phases", default="all", help="e.g. 'all' (default), 'ics,pf', 'coeval'")
    ap.add_argument("--results-root", type=Path, default=Path("scaling/results"))
    ap.add_argument("--sim-root", type=Path, default=Path("scaling/sims"),
                    help="where simulation caches live (must be persistent storage to allow resuming)")
    ap.add_argument("--keep-sim", action="store_true", help="do not delete the simulation cache when complete")
    ap.add_argument("--restart", action="store_true", help="archive previous results of this configuration and start over")
    ap.add_argument("--redo-from", choices=PHASES, help="re-measure this phase and all downstream phases")
    ap.add_argument("--coeval-batch", type=int, default=0, metavar="N",
                    help="measure coevals like production batch jobs (run_N_coevals.py): a fresh process "
                         "per N redshifts, each re-reading the history from the cache. 0 (default): the full "
                         "evolution in one process. Results go to ..._CBNN/")
    ap.add_argument("--expect-version", default=None,
                    help="regex the installed py21cmfast version must match (guards against a wrong venv)")
    ap.add_argument("--sample-interval", type=float, default=1.0, help="RSS time-series sampling interval [s]")
    ap.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING"))
    ap.add_argument("--break-lock", action="store_true", help="ignore an existing lock (only if you are sure)")
    args = ap.parse_args(argv)

    if args.hii_dim <= 0 or args.n_threads <= 0 or args.seed < 0 or args.sample_interval <= 0 or args.coeval_batch < 0:
        ap.error("--hii-dim, --n-threads, --sample-interval must be positive and --seed non-negative")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.label):
        ap.error("--label may only contain letters, digits, '.', '_' and '-'")
    try:
        parse_phases(args.phases)
    except ValueError as exc:
        ap.error(str(exc))
    for name in ("template", "results_root", "sim_root"):
        p = getattr(args, name)
        setattr(args, name, (p if p.is_absolute() else EOS26_ROOT / p).resolve())
    if not args.template.is_file():
        ap.error(f"template not found: {args.template}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return Driver(args).main()
    except LockedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 75


if __name__ == "__main__":
    sys.exit(main())
