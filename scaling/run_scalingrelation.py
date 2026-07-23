#!/usr/bin/env python3
"""Fit and plot scaling relations from run_scaling.py JSON measurements."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PHASE_LABELS = {
    "ics": "Initial conditions",
    "pf": "One perturbed field",
    "phf": "Perturbed halo fields",
    "coeval": "One coeval",
}
README_PHASE_LABELS = {
    **PHASE_LABELS,
    "coeval": "Evolving astrophysics for one coeval",
}
README_STORAGE_EXCLUSIONS = {"IonizedBox"}
FIXED_RELATIVE_POINT_ERROR = 0.10
COEVAL_STORAGE_COUNT = 92

# Peak RSS for 3D simulation grids is physically fixed per-process overhead
# plus a term that scales with box volume (HII_DIM**3), so memory is fit with
# an affine model in HII_DIM**3 (see fit_affine) rather than a free-exponent
# power law.
NODE_MEMORY_BUDGET_BYTES = 3.0e12  # target node RAM (3.0 TB, decimal)
NODE_MEMORY_SAFETY_BUDGET_BYTES = 2.7e12  # 90% of budget: headroom for OS/cache/other overhead
PROJECTION_RESOLUTION_MPC = 1.5  # cMpc/cell, fixed; only HII_DIM is varied
MEMORY_METRICS = {"peak_rss_bytes", "rss_above_baseline_bytes"}

# With only 3 measured points, the coeval phase's affine memory fit is pulled
# noticeably off the data by whichever point dominates the linear-space sum
# of squares. A free-exponent power-law fit (already used for time/storage,
# see fit_power_law) tracks the coeval measurements markedly better in this
# case, so it is computed and shown alongside the affine fit for this phase
# only -- purely as a comparison; the affine model remains the one used for
# the README's budget/EOS-target projections.
COEVAL_COMPARISON_METRICS = {"peak_rss_bytes"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=ROOT / "scaling" / "results",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "scaling" / "reports",
    )
    parser.add_argument(
        "--target-dims",
        default="120,240,1200,1400",
        help="Comma-separated HII_DIM values to include in extrapolated tables",
    )
    parser.add_argument(
        "--update-readme",
        action="store_true",
        help="Update README measurements and fitted extrapolation intervals",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=ROOT / "README.md",
        help="README path used with --update-readme",
    )
    return parser.parse_args()


def read_records(results_dir: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(results_dir.glob("scaling_HII_DIM_*.json")):
        with path.open() as handle:
            record = json.load(handle)
        if not record.get("phases"):
            continue
        records.append(record)
    records.sort(key=lambda record: record["hii_dim"])
    if len({record["hii_dim"] for record in records}) < 2:
        raise RuntimeError("At least two distinct HII_DIM result files are required")
    return records


def fit_power_law(dimensions: np.ndarray, values: np.ndarray) -> dict[str, float]:
    """Fit y = coefficient * HII_DIM ** exponent with log-space uncertainty."""
    valid = values > 0
    if valid.sum() < 2:
        raise ValueError("Need two positive measurements to fit a scaling relation")
    log_dimensions = np.log(dimensions[valid])
    log_values = np.log(values[valid])
    n = len(log_dimensions)
    log_u_bar = float(log_dimensions.mean())
    log_v_bar = float(log_values.mean())
    log_sxx = float(np.sum((log_dimensions - log_u_bar) ** 2))
    log_sxy = float(np.sum((log_dimensions - log_u_bar) * (log_values - log_v_bar)))
    exponent = log_sxy / log_sxx
    log_coefficient = log_v_bar - exponent * log_u_bar

    residuals = log_values - (log_coefficient + exponent * log_dimensions)
    dof = n - 2
    log_residual_variance = float(np.sum(residuals ** 2) / dof) if dof > 0 else 0.0

    return {
        "kind": "power_law",
        "coefficient": float(np.exp(log_coefficient)),
        "exponent": float(exponent),
        "log_u_bar": log_u_bar,
        "log_sxx": log_sxx,
        "log_residual_variance": log_residual_variance,
        "n": n,
    }


def fit_affine(dimensions: np.ndarray, values: np.ndarray) -> dict[str, float]:
    """Fit y = intercept + slope * HII_DIM ** 3 by ordinary least squares.

    Peak memory for a 3D grid-based simulation is physically fixed
    per-process overhead (interpreter, shared libraries, lookup tables) plus
    a term that scales with box volume (HII_DIM**3). Fitting this affine form
    directly -- using *all* available measurements -- avoids the bias a
    free-exponent log-log power-law fit shows when overhead is not negligible
    at small HII_DIM (see fit_power_law), without discarding any data the way
    anchoring on a single point would.
    """
    valid = values > 0
    if valid.sum() < 2:
        raise ValueError("Need two positive measurements to fit an affine memory model")
    x = dimensions[valid] ** 3
    y = values[valid]
    n = len(x)
    x_bar = float(x.mean())
    y_bar = float(y.mean())
    sxx = float(np.sum((x - x_bar) ** 2))
    sxy = float(np.sum((x - x_bar) * (y - y_bar)))
    slope = sxy / sxx
    intercept = y_bar - slope * x_bar

    residuals = y - (intercept + slope * x)
    dof = n - 2
    residual_variance = float(np.sum(residuals ** 2) / dof) if dof > 0 else 0.0

    return {
        "kind": "affine",
        "intercept": float(intercept),
        "slope": float(slope),
        "x_bar": x_bar,
        "sxx": sxx,
        "residual_variance": residual_variance,
        "n": n,
    }


def predict(fit: dict[str, float], dimension: float) -> float:
    if fit["kind"] == "power_law":
        return fit["coefficient"] * dimension ** fit["exponent"]
    return fit["intercept"] + fit["slope"] * dimension ** 3


def prediction_interval(fit: dict[str, float], dimension: float) -> tuple[float, float]:
    """Return (mean - 1 sigma, mean + 1 sigma) for the fitted value.

    The regression's own confidence-interval-on-the-mean (from residual
    variance and distance from the data's center, in log-space for power-law
    fits and linear space for the affine memory fit) is combined in
    quadrature with a fixed 10% relative per-point measurement-uncertainty
    floor, so a fit that happens to pass close to its few points does not
    imply implausibly tight confidence.
    """
    value = predict(fit, dimension)
    if fit["kind"] == "power_law":
        u0 = np.log(dimension)
        fit_log_sigma = np.sqrt(
            fit["log_residual_variance"]
            * (1.0 / fit["n"] + (u0 - fit["log_u_bar"]) ** 2 / fit["log_sxx"])
        )
        log_sigma = float(np.hypot(fit_log_sigma, np.log1p(FIXED_RELATIVE_POINT_ERROR)))
        return value * np.exp(-log_sigma), value * np.exp(log_sigma)

    x0 = dimension ** 3
    fit_sigma = np.sqrt(
        fit["residual_variance"] * (1.0 / fit["n"] + (x0 - fit["x_bar"]) ** 2 / fit["sxx"])
    )
    sigma = float(np.hypot(fit_sigma, FIXED_RELATIVE_POINT_ERROR * value))
    return value - sigma, value + sigma


def mean_and_sigma(fit: dict[str, float], dimension: float) -> tuple[float, float]:
    """Return (mean, 1-sigma) for the fitted value at `dimension`."""
    value = predict(fit, dimension)
    lower, upper = prediction_interval(fit, dimension)
    return value, (upper - lower) / 2.0


def max_dimension_for_budget(
    fit: dict[str, float], budget_bytes: float, conservative: bool = True
) -> float:
    """Find the largest HII_DIM whose predicted value stays within budget_bytes.

    When conservative is True, the *upper* end of the 1-sigma interval (not
    just the central estimate) is required to stay within budget, so the
    returned dimension is safe even if the true value runs high within the
    estimated uncertainty. Solved numerically (bisection) since the sigma
    itself depends on the target dimension, so the budget cannot generally be
    inverted in closed form.
    """
    def value_at(dimension: float) -> float:
        if conservative:
            return prediction_interval(fit, dimension)[1]
        return predict(fit, dimension)

    lo, hi = 1.0, 2.0
    while value_at(hi) < budget_bytes:
        hi *= 2.0
        if hi > 1e6:
            raise RuntimeError("Could not bracket a dimension for the given memory budget")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if value_at(mid) < budget_bytes:
            lo = mid
        else:
            hi = mid
    return lo


def phase_storage_bytes(phase: str, result: dict[str, Any]) -> int:
    files = result["files"]
    excluded = README_STORAGE_EXCLUSIONS if phase == "coeval" else set()
    return sum(item["bytes"] for name, item in files.items() if name not in excluded)


def series(records: list[dict[str, Any]], phase: str, metric: str) -> tuple[np.ndarray, np.ndarray]:
    dimensions = []
    values = []
    for record in records:
        result = record["phases"].get(phase)
        if result is None:
            continue
        dimensions.append(record["hii_dim"])
        if metric == "storage_bytes":
            values.append(phase_storage_bytes(phase, result))
        else:
            values.append(result[metric])
    return np.asarray(dimensions, dtype=float), np.asarray(values, dtype=float)


def file_series(records: list[dict[str, Any]], file_type: str) -> tuple[np.ndarray, np.ndarray]:
    dimensions = []
    values = []
    for record in records:
        total = sum(
            result["files"].get(file_type, {}).get("bytes", 0)
            for result in record["phases"].values()
        )
        if total:
            dimensions.append(record["hii_dim"])
            values.append(total)
    return np.asarray(dimensions, dtype=float), np.asarray(values, dtype=float)


def plot_phase_metrics(records: list[dict[str, Any]], output_dir: Path) -> None:
    metrics = (
        ("peak_rss_bytes", "Peak RSS (GiB)"),
        ("elapsed_seconds", "Elapsed time (s)"),
        ("storage_bytes", "Storage (GiB)"),
    )
    figure, axes = plt.subplots(1, len(metrics), figsize=(15, 4.8))
    for axis, (metric, label) in zip(axes, metrics):
        for phase, phase_label in PHASE_LABELS.items():
            dimensions, values = series(records, phase, metric)
            if len(dimensions) < 2 or not np.all(values > 0):
                continue
            fit = (
                fit_affine(dimensions, values)
                if metric in MEMORY_METRICS
                else fit_power_law(dimensions, values)
            )
            points = axis.loglog(
                dimensions, values / 2**30 if "bytes" in metric else values, "o", label=phase_label
            )
            model_x = np.geomspace(dimensions.min(), dimensions.max(), 100)
            model_y = np.array([predict(fit, value) for value in model_x])
            axis.loglog(model_x, model_y / 2**30 if "bytes" in metric else model_y, "-", color=points[0].get_color())
            # For coeval memory metrics, also show a free-exponent power-law fit
            # for comparison -- it empirically tracks the measured points
            # noticeably better than the affine model at this phase (see
            # COEVAL_COMPARISON_METRICS), even though the affine model remains
            # the one used for the README's budget/EOS projections.
            if phase == "coeval" and metric in COEVAL_COMPARISON_METRICS:
                alt_fit = fit_power_law(dimensions, values)
                alt_model_y = np.array([predict(alt_fit, value) for value in model_x])
                axis.loglog(
                    model_x,
                    alt_model_y / 2**30 if "bytes" in metric else alt_model_y,
                    "--",
                    color=points[0].get_color(),
                    label=f"{phase_label} (power law)",
                )
        axis.set_xlabel("HII_DIM")
        axis.set_ylabel(label)
        axis.grid(True, which="both", alpha=0.25)
    axes[0].legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(output_dir / "phase_scaling.png", dpi=180)
    plt.close(figure)


def plot_file_sizes(records: list[dict[str, Any]], output_dir: Path) -> None:
    file_types = sorted({name for record in records for phase in record["phases"].values() for name in phase["files"]})
    figure, axis = plt.subplots(figsize=(7, 5))
    for file_type in file_types:
        dimensions, values = file_series(records, file_type)
        if len(dimensions) < 2 or not np.all(values > 0):
            continue
        fit = fit_power_law(dimensions, values)
        axis.loglog(dimensions, values / 2**30, "o", label=file_type)
        model_x = np.geomspace(dimensions.min(), dimensions.max(), 100)
        axis.loglog(model_x, [predict(fit, value) / 2**30 for value in model_x], "-")
    axis.set_xlabel("HII_DIM")
    axis.set_ylabel("HDF5 size (GiB)")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend(fontsize="small")
    figure.tight_layout()
    figure.savefig(output_dir / "file_size_scaling.png", dpi=180)
    plt.close(figure)


def fitted_metrics(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, float]]]:
    fits: dict[str, dict[str, dict[str, float]]] = {}
    for phase in PHASE_LABELS:
        phase_fits: dict[str, dict[str, float]] = {}
        for metric in ("elapsed_seconds", "peak_rss_bytes", "rss_above_baseline_bytes", "storage_bytes"):
            dimensions, values = series(records, phase, metric)
            if len(dimensions) < 2 or not np.all(values > 0):
                continue
            if metric in MEMORY_METRICS:
                phase_fits[metric] = fit_affine(dimensions, values)
                if phase == "coeval" and metric in COEVAL_COMPARISON_METRICS:
                    phase_fits[f"{metric}_power_law"] = fit_power_law(dimensions, values)
            else:
                phase_fits[metric] = fit_power_law(dimensions, values)
        if phase_fits:
            fits[phase] = phase_fits
    return fits


def fitted_file_sizes(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Fit every stored HDF5 structure that has two positive measurements."""
    file_types = {
        name
        for record in records
        for phase in record["phases"].values()
        for name in phase["files"]
    }
    fits = {}
    for file_type in sorted(file_types):
        dimensions, values = file_series(records, file_type)
        if len(dimensions) >= 2 and np.all(values > 0):
            fits[file_type] = fit_power_law(dimensions, values)
    return fits


def format_gib(value: float) -> str:
    return f"{value / 2**30:.3g} GiB"


def format_readme_hours(seconds: float) -> str:
    return f"{seconds / 3600:.3g}"


def format_readme_tb(bytes_: float) -> str:
    return f"{bytes_ / 1e12:.3g} TB"


def format_readme_gb(bytes_: float) -> str:
    return f"{bytes_ / 1e9:.3g} GB"


def _split_number_unit(formatted: str) -> tuple[str, str]:
    parts = formatted.split(" ", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ""


def format_mean_sigma(
    fit: dict[str, float],
    dimension: int,
    formatter: Any,
) -> str:
    """Format the fit's mean prediction plus/minus 1 sigma using `formatter` for units."""
    value, sigma = mean_and_sigma(fit, dimension)
    value_str, unit = _split_number_unit(formatter(value))
    sigma_str, _ = _split_number_unit(formatter(sigma))
    suffix = f" {unit}" if unit else ""
    return f"{value_str} \u00b1 {sigma_str}{suffix}"


def format_coeval_storage(value: float, formatter: Any) -> str:
    """Format one coeval's storage and the total for all node redshifts."""
    return f"{formatter(value)} x {COEVAL_STORAGE_COUNT} = {formatter(value * COEVAL_STORAGE_COUNT)}"


def format_coeval_storage_mean_sigma(
    fit: dict[str, float],
    dimension: int,
    formatter: Any,
) -> str:
    """Format fitted per-coeval storage mean +/- 1 sigma and its all-redshift total."""
    value, sigma = mean_and_sigma(fit, dimension)
    value_str, unit = _split_number_unit(formatter(value))
    sigma_str, _ = _split_number_unit(formatter(sigma))
    total_value_str, _ = _split_number_unit(formatter(value * COEVAL_STORAGE_COUNT))
    total_sigma_str, _ = _split_number_unit(formatter(sigma * COEVAL_STORAGE_COUNT))
    suffix = f" {unit}" if unit else ""
    return (
        f"{value_str} \u00b1 {sigma_str}{suffix} x {COEVAL_STORAGE_COUNT} = "
        f"{total_value_str} \u00b1 {total_sigma_str}{suffix}"
    )


def update_readme_measured_table(
    readme_path: Path,
    records: list[dict[str, Any]],
    fits: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Update direct extrema measurements and fitted extrapolation intervals."""
    needed_metrics = ("elapsed_seconds", "peak_rss_bytes", "storage_bytes")
    missing = [
        phase
        for phase in PHASE_LABELS
        if not all(metric in fits.get(phase, {}) for metric in needed_metrics)
    ]
    if missing:
        raise RuntimeError(
            "README update requires time, memory, and storage fits for all phases; "
            f"missing: {', '.join(missing)}"
        )

    smallest_record, largest_record = records[0], records[-1]
    measured_records = (smallest_record, largest_record)
    for record in measured_records:
        for phase in PHASE_LABELS:
            result = record["phases"].get(phase)
            if result is None:
                raise RuntimeError(
                    f"README update requires {phase} results at HII_DIM={record['hii_dim']}"
                )
            missing = [
                metric
                for metric in needed_metrics[:-1]
                if result.get(metric, 0) <= 0
            ]
            if missing or phase_storage_bytes(phase, result) <= 0:
                details = missing + (["storage_bytes"] if phase_storage_bytes(phase, result) <= 0 else [])
                raise RuntimeError(
                    f"README update requires positive measurements for {phase} at "
                    f"HII_DIM={record['hii_dim']}; missing: {', '.join(details)}"
                )

    text = readme_path.read_text()
    start_marker = '<tr><td colspan="7"><em>Scaling tests (measured)</em></td></tr>'
    end_marker = '<tr><td colspan="7"><em>Extrapolated to EOS-1'
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start == -1 or end == -1:
        raise RuntimeError("Could not find the measured scaling-table section in README")

    table_start = text.rfind("<table", 0, start)
    if table_start == -1:
        raise RuntimeError("Could not find the scaling table in README")
    header = text[table_start:start]
    dimensions = (smallest_record["hii_dim"], largest_record["hii_dim"])
    header, replacements = re.subn(
        r"<th>N=\d+</th>\s*<th>N=\d+</th>",
        f"<th>N={dimensions[0]}</th>\n    <th>N={dimensions[1]}</th>",
        header,
        count=3,
    )
    if replacements != 3:
        raise RuntimeError("Could not update the three measured-dimension headers in README")

    section = text[start:end]
    for phase, label in README_PHASE_LABELS.items():
        phase_results = [record["phases"][phase] for record in measured_records]
        new_values = [format_readme_hours(result["elapsed_seconds"]) for result in phase_results]
        new_values += [format_readme_gb(result["peak_rss_bytes"]) for result in phase_results]
        storage_formatter = (
            lambda result: format_coeval_storage(phase_storage_bytes(phase, result), format_readme_gb)
            if phase == "coeval"
            else format_readme_gb(phase_storage_bytes(phase, result))
        )
        new_values += [storage_formatter(result) for result in phase_results]
        pattern = re.compile(
            rf"(?P<prefix><tr>\s*<td>{re.escape(label)}</td>)(?P<cells>.*?)(?P<suffix></tr>)",
            re.DOTALL,
        )
        match = pattern.search(section)
        if match is None:
            raise RuntimeError(f"Could not find README row for {label}")
        cells = re.findall(r"<td(?:\s+[^>]*)?>.*?</td>", match.group("cells"), re.DOTALL)
        if len(cells) != 6:
            raise RuntimeError(f"Expected six value cells in README row for {label}, found {len(cells)}")
        cells = [f"<td>{value}</td>" for value in new_values]
        replacement = match.group("prefix") + "\n    " + "\n    ".join(cells) + "\n  " + match.group("suffix")
        section = section[:match.start()] + replacement + section[match.end():]

    text = text[:table_start] + header + section + text[end:]
    extrapolated_sections = re.compile(
        r"(?P<marker><tr><td colspan=\"7\"><em>Extrapolated to EOS-\d+ "
        r"\(HII_DIM = (?P<dimension>\d+),.*?</em></td></tr>)(?P<rows>.*?)"
        r"(?=(?:<tr><td colspan=\"7\"><em>Extrapolated to EOS-|</tbody>))",
        re.DOTALL,
    )

    def update_extrapolated_section(match: re.Match[str]) -> str:
        rows = match.group("rows")
        dimension = int(match.group("dimension"))
        for phase, label in README_PHASE_LABELS.items():
            metrics = fits[phase]
            values = [
                format_mean_sigma(metrics["elapsed_seconds"], dimension, format_readme_hours),
                format_mean_sigma(metrics["peak_rss_bytes"], dimension, format_readme_tb),
                (
                    format_coeval_storage_mean_sigma(metrics["storage_bytes"], dimension, format_readme_tb)
                    if phase == "coeval"
                    else format_mean_sigma(metrics["storage_bytes"], dimension, format_readme_tb)
                ),
            ]
            pattern = re.compile(
                rf"(?P<prefix><tr>\s*<td>{re.escape(label)}</td>)(?P<cells>.*?)(?P<suffix></tr>)",
                re.DOTALL,
            )
            row = pattern.search(rows)
            if row is None:
                raise RuntimeError(f"Could not find extrapolated README row for {label}")
            replacement = (
                row.group("prefix")
                + "\n    "
                + "\n    ".join(f'<td colspan="2">{value}</td>' for value in values)
                + "\n  "
                + row.group("suffix")
            )
            rows = rows[:row.start()] + replacement + rows[row.end():]
        return match.group("marker") + rows

    text, replacements = extrapolated_sections.subn(update_extrapolated_section, text)
    if replacements != 2:
        raise RuntimeError("Could not update both extrapolated scaling-table sections in README")
    readme_path.write_text(text)


def update_readme_projection_table(
    readme_path: Path,
    fits: dict[str, dict[str, dict[str, float]]],
    records: list[dict[str, Any]],
) -> None:
    """Insert or update the projected-maximum-simulation-size section.

    Uses the coeval phase's peak-RSS fit (an affine model in HII_DIM**3,
    fit by ordinary least squares on all measured points) since evolving
    astrophysics for one coeval is the most memory-intensive phase at every
    measured HII_DIM.
    """
    coeval_fit = fits.get("coeval", {}).get("peak_rss_bytes")
    if coeval_fit is None:
        raise RuntimeError("README projection requires a coeval peak_rss_bytes fit")
    coeval_power_law_fit = fits.get("coeval", {}).get("peak_rss_bytes_power_law")
    measured_dims = sorted(int(record["hii_dim"]) for record in records)

    budgets = (
        ("3.0 TB", NODE_MEMORY_BUDGET_BYTES),
        ("2.7 TB (90% safety margin)", NODE_MEMORY_SAFETY_BUDGET_BYTES),
    )
    eos_targets = (("EOS-1", 1400), ("EOS-2", 1200))

    lines = [
        "## Projected maximum simulation size",
        "",
        (
            "Evolving astrophysics for one coeval is the most memory-intensive phase at "
            "every measured `HII_DIM` (see table above), so it sets the ceiling for the "
            "largest simulation a single node can run. Peak memory for 3D simulation grids "
            "is physically fixed per-process overhead (interpreter, shared libraries, lookup "
            "tables) plus a term that scales with box volume (`HII_DIM^3`), so peak RSS is "
            "fit as `overhead + coefficient * HII_DIM^3` by ordinary least squares using *all* "
            f"measured points (`HII_DIM` = {', '.join(str(d) for d in measured_dims)}), rather "
            "than a free-exponent log-log power law, which is biased low by that same fixed "
            "overhead when it is not negligible at small `HII_DIM` (the same effect documented "
            "above for compute time). "
            f"Resolution is fixed at {PROJECTION_RESOLUTION_MPC} cMpc/cell, matching all "
            "current scaling points; only `HII_DIM` is varied. The \"Max HII_DIM\" columns "
            "require the upper end of the fit's 1-sigma band to stay within the memory budget, "
            "so the true peak should stay at or below the stated value."
        ),
        "",
        "<table><thead>",
        "  <tr>",
        "    <th>Memory budget</th>",
        "    <th>Max HII_DIM</th>",
        "    <th>Box length [Mpc]</th>",
        "    <th>Predicted peak RSS (coeval)</th>",
        "  </tr>",
        "</thead>",
        "<tbody>",
    ]
    for label, budget in budgets:
        dim_max = int(max_dimension_for_budget(coeval_fit, budget, conservative=True))
        lines.extend(
            [
                "  <tr>",
                f"    <td>{label}</td>",
                f"    <td>{dim_max}</td>",
                f"    <td>{dim_max * PROJECTION_RESOLUTION_MPC:.0f}</td>",
                f"    <td>{format_mean_sigma(coeval_fit, dim_max, format_readme_tb)}</td>",
                "  </tr>",
            ]
        )
    lines.append("</tbody></table>")
    lines.append("")
    lines.append(
        "Predicted coeval peak RSS at the current EOS target sizes "
        "(affine `overhead + coefficient * HII_DIM^3` fit on all measured points):"
    )
    lines.append("")
    lines.append("<table><thead>")
    lines.append("  <tr><th>EOS target</th><th>HII_DIM</th><th>Predicted peak RSS (coeval)</th></tr>")
    lines.append("</thead>")
    lines.append("<tbody>")
    for name, dim in eos_targets:
        lines.append(
            f"  <tr><td>{name}</td><td>{dim}</td>"
            f"<td>{format_mean_sigma(coeval_fit, dim, format_readme_tb)}</td></tr>"
        )
    lines.append("</tbody></table>")
    lines.append("")
    if coeval_power_law_fit is not None:
        lines.append(
            "With only 3 measured points, the affine fit above is pulled noticeably off "
            "the data by whichever point dominates the linear-space sum of squares. A "
            "free-exponent power-law fit (the same form used for time and storage; see "
            "`fit_power_law`) tracks the coeval measurements markedly better, so it is "
            "shown here for comparison -- the affine model above remains the one used for "
            "the Max HII_DIM budget table:"
        )
        lines.append("")
        lines.append("<table><thead>")
        lines.append(
            "  <tr><th>EOS target</th><th>HII_DIM</th>"
            "<th>Predicted peak RSS, affine</th><th>Predicted peak RSS, power law</th></tr>"
        )
        lines.append("</thead>")
        lines.append("<tbody>")
        for name, dim in eos_targets:
            lines.append(
                f"  <tr><td>{name}</td><td>{dim}</td>"
                f"<td>{format_mean_sigma(coeval_fit, dim, format_readme_tb)}</td>"
                f"<td>{format_mean_sigma(coeval_power_law_fit, dim, format_readme_tb)}</td></tr>"
            )
        lines.append("</tbody></table>")
        lines.append("")
    lines.append(
        "**Caveats:** this projection extrapolates well beyond the largest measured "
        f"`HII_DIM` ({measured_dims[-1]}) to production scale, so treat it as an "
        "order-of-magnitude estimate rather than a precise bound. Run an additional scaling "
        "point at `HII_DIM = 400` (or larger) on the cluster and check whether the residuals "
        "from the affine fit stay small -- growing residuals at larger `HII_DIM` would mean "
        "memory grows faster than the assumed overhead-plus-cubic form and this projection is "
        "optimistic. Consider also profiling one run with `memray` to see the full "
        "memory-vs-redshift curve and confirm the RSS sampler is not missing any brief spikes."
    )

    text = readme_path.read_text()
    section_text = "\n".join(lines).rstrip("\n") + "\n"
    heading = "## Projected maximum simulation size"
    existing_pattern = re.compile(re.escape(heading) + r"\n.*?(?=\n## |\Z)", re.DOTALL)
    if existing_pattern.search(text):
        text = existing_pattern.sub(lambda _match: section_text, text, count=1)
    else:
        anchor = "## Scaling test results"
        anchor_index = text.find(anchor)
        if anchor_index == -1:
            raise RuntimeError("Could not find the '## Scaling test results' section in README")
        table_end_marker = "</tbody></table>"
        table_end = text.find(table_end_marker, anchor_index)
        if table_end == -1:
            raise RuntimeError("Could not find the scaling table's closing tag in README")
        insert_at = table_end + len(table_end_marker)
        text = text[:insert_at] + "\n\n" + section_text + text[insert_at:]
    readme_path.write_text(text)


def write_readme_values(
    records: list[dict[str, Any]],
    fits: dict[str, dict[str, dict[str, float]]],
    file_fits: dict[str, dict[str, float]],
    targets: list[int],
    output_dir: Path,
) -> None:
    lines = [
        "# Scaling Values for README",
        "",
        "Generated by `scaling/run_scalingrelation.py`. Storage for the coeval row excludes `IonizedBox`, matching the README convention. Extrapolated values are mean \u00b1 1-sigma from a regression fit to all available scaling points (affine `overhead + coefficient * HII_DIM^3` for peak RSS, power law for time and storage).",
        "",
        "## Measured Values",
        "",
        "| Phase | HII_DIM | Time | Peak RSS | Storage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for record in records:
        for phase, label in PHASE_LABELS.items():
            result = record["phases"].get(phase)
            if result is None:
                continue
            lines.append(
                f"| {label} | {record['hii_dim']} | {result['elapsed_seconds']:.3g} s | "
                f"{format_gib(result['peak_rss_bytes'])} | "
                f"{format_coeval_storage(phase_storage_bytes(phase, result), format_gib) if phase == 'coeval' else format_gib(phase_storage_bytes(phase, result))} |"
            )

    lines.extend([
        "",
        "## Fitted Extrapolations",
        "",
        "| Phase | HII_DIM | Time | Peak RSS | Storage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ])
    for target in targets:
        for phase, label in PHASE_LABELS.items():
            phase_fits = fits.get(phase, {})
            needed = ("elapsed_seconds", "peak_rss_bytes", "storage_bytes")
            if not all(metric in phase_fits for metric in needed):
                continue
            lines.append(
                f"| {label} | {target} | {format_mean_sigma(phase_fits['elapsed_seconds'], target, format_readme_hours)} h | "
                f"{format_mean_sigma(phase_fits['peak_rss_bytes'], target, format_gib)} | "
                f"{format_coeval_storage_mean_sigma(phase_fits['storage_bytes'], target, format_gib) if phase == 'coeval' else format_mean_sigma(phase_fits['storage_bytes'], target, format_gib)} |"
            )

    coeval_power_law_fit = fits.get("coeval", {}).get("peak_rss_bytes_power_law")
    if coeval_power_law_fit is not None:
        lines.extend([
            "",
            "## Coeval Peak RSS: Affine vs Power-Law Fit Comparison",
            "",
            (
                "With only 3 measured points, the affine fit is pulled noticeably off the "
                "data by whichever point dominates the linear-space sum of squares; a "
                "free-exponent power-law fit tracks the coeval measurements markedly "
                "better. The affine fit remains the one used elsewhere in this document "
                "(including the projected-maximum-simulation-size budget table)."
            ),
            "",
            "| HII_DIM | Peak RSS, affine | Peak RSS, power law |",
            "| ---: | ---: | ---: |",
        ])
        for target in targets:
            lines.append(
                f"| {target} | {format_mean_sigma(fits['coeval']['peak_rss_bytes'], target, format_gib)} | "
                f"{format_mean_sigma(coeval_power_law_fit, target, format_gib)} |"
            )

    lines.extend([
        "",
        "## File-Size Extrapolations",
        "",
        "| HDF5 structure | HII_DIM | Storage |",
        "| --- | ---: | ---: |",
    ])
    for target in targets:
        for file_type, fit in file_fits.items():
            lines.append(
                f"| {file_type} | {target} | {format_mean_sigma(fit, target, format_gib)} |"
            )

    (output_dir / "README_scaling_values.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    args = parse_args()
    targets = [int(value) for value in args.target_dims.split(",") if value.strip()]
    records = read_records(args.results_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fits = fitted_metrics(records)
    file_fits = fitted_file_sizes(records)
    plot_phase_metrics(records, args.output_dir)
    plot_file_sizes(records, args.output_dir)
    write_readme_values(records, fits, file_fits, targets, args.output_dir)
    summary = {
        "source_dimensions": [record["hii_dim"] for record in records],
        "phase_fits": fits,
        "file_size_fits": file_fits,
        "targets": {
            str(target): {
                "phases": {
                    phase: {metric: predict(fit, target) for metric, fit in metrics.items()}
                    for phase, metrics in fits.items()
                },
                "file_sizes": {file_type: predict(fit, target) for file_type, fit in file_fits.items()},
            }
            for target in targets
        },
    }
    (args.output_dir / "scaling_fits.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if args.update_readme:
        update_readme_measured_table(args.readme, records, fits)
        update_readme_projection_table(args.readme, fits, records)
        print(f"Updated scaling values in {args.readme}")
    print(f"Wrote reports to {args.output_dir}")


if __name__ == "__main__":
    main()
