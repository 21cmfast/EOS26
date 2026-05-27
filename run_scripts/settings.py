"""Shared configuration and utilities for all EOS run scripts."""

import os
import logging
import argparse
import psutil
from datetime import datetime

# ── template ───────────────────────────────────────────────────────────────

TEMPLATE_NAME = "EOS25.toml"

# ── cache directories ──────────────────────────────────────────────────────

# Main EOS25 cache (used by run_ICs and run_PHFs)
CACHE_FULL  = '/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2000_HIIDIM1200_DIM3600/'
# N_PFs cache (separate path/location)
CACHE_NPFS  = 'ocean/projects/phy210034p/breitman/messy/EOS25/EOS25_L2000_HIIDIM1200_DIM3600'
# Alternative cache (used by run_PFs and run_N_coevals)
CACHE_ALT   = '/ocean/projects/phy210034p/breitman/EOS25/EOS25_L2100_HIIDIM1400_DIM4200'
# Small test cache
CACHE_TEST  = '/ocean/projects/phy210034p/breitman/EOS25/EOS25_test_HIIDIM200/'

# ── simulation parameters ──────────────────────────────────────────────────

RANDOM_SEED     = 42    # used by run_ICs, run_N_PFs, run_PHFs
RANDOM_SEED_ALT = 1234  # used by run_PFs, run_N_coevals
TEST_HII_DIM    = 200

# Clear DIM / BOX_LEN from the TOML and derive them from the ratio / cell-size
# instead, so --test only needs to override HII_DIM.
TEMPLATE_BOX_KWARGS = dict(
    DIM=None,
    BOX_LEN=None,
    HIRES_TO_LOWRES_FACTOR=3,
    LOWRES_CELL_SIZE_MPC=1.666666,
)

# ── memory tracking ────────────────────────────────────────────────────────

PROCESS = psutil.Process(os.getpid())
_PEAK_RSS_BYTES: int = PROCESS.memory_info().rss


def now_str() -> str:
    """Return the current wall-clock time as a formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def peak_rss_gb() -> float:
    """Return peak RSS memory usage in GB since process start."""
    global _PEAK_RSS_BYTES
    rss = PROCESS.memory_info().rss
    if rss > _PEAK_RSS_BYTES:
        _PEAK_RSS_BYTES = rss
    return _PEAK_RSS_BYTES / (1024.0 ** 3)


# ── logging ────────────────────────────────────────────────────────────────

class _RSSFilter(logging.Filter):
    """Inject the current RSS (in GB) into every log record as ``rss_gb``."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.rss_gb = PROCESS.memory_info().rss / (1024.0 ** 3)  # type: ignore[attr-defined]
        return True


def setup_logging(log_file: str) -> logging.Logger:
    """Configure the 21cmFAST logger to write to *log_file* and return it.

    Each log line includes the current RSS so memory growth is visible
    alongside the computation progress without needing explicit probes.
    """
    logger = logging.getLogger("21cmFAST")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.FileHandler(log_file)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - [RSS %(rss_gb).3f GB] - %(message)s")
    )
    handler.addFilter(_RSSFilter())
    logger.addHandler(handler)
    return logger


# ── argument parsing ───────────────────────────────────────────────────────

def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add --log-file and --test to *parser* (shared by all run scripts)."""
    parser.add_argument("--log-file", type=str, required=True)
    parser.add_argument(
        "--test", action="store_true", default=False,
        help=f"Run a small test box (HII_DIM={TEST_HII_DIM}) instead of the full EOS",
    )


# ── run configuration ──────────────────────────────────────────────────────

def resolve_run_config(test: bool, full_cache_dir: str) -> tuple[str, dict]:
    """Return *(cache_dir, box_overrides)* for the given --test flag."""
    if test:
        return CACHE_TEST, dict(HII_DIM=TEST_HII_DIM)
    return full_cache_dir, {}
