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
        help="Update README measured cells from the smallest and largest HII_DIM runs",
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
    """Fit y = coefficient * HII_DIM ** exponent for positive measurements."""
    valid = values > 0
    if valid.sum() < 2:
        raise ValueError("Need two positive measurements to fit a scaling relation")
    exponent, log_coefficient = np.polyfit(np.log(dimensions[valid]), np.log(values[valid]), 1)
    return {"coefficient": float(np.exp(log_coefficient)), "exponent": float(exponent)}


def predict(fit: dict[str, float], dimension: int) -> float:
    return fit["coefficient"] * dimension ** fit["exponent"]


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
            fit = fit_power_law(dimensions, values)
            axis.loglog(dimensions, values / 2**30 if "bytes" in metric else values, "o", label=phase_label)
            model_x = np.geomspace(dimensions.min(), dimensions.max(), 100)
            model_y = np.array([predict(fit, value) for value in model_x])
            axis.loglog(model_x, model_y / 2**30 if "bytes" in metric else model_y, "-")
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
            if len(dimensions) >= 2 and np.all(values > 0):
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


def update_readme_measured_table(
    readme_path: Path,
    records: list[dict[str, Any]],
    fits: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Update extrema measurements while retaining extrapolated rows."""
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
        new_values += [format_readme_tb(result["peak_rss_bytes"]) for result in phase_results]
        new_values += [format_readme_tb(phase_storage_bytes(phase, result)) for result in phase_results]
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

    readme_path.write_text(text[:table_start] + header + section + text[end:])


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
        "Generated by `scaling/run_scalingrelation.py`. Storage for the coeval row excludes `IonizedBox`, matching the README convention.",
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
                f"{format_gib(result['peak_rss_bytes'])} | {format_gib(phase_storage_bytes(phase, result))} |"
            )

    lines.extend([
        "",
        "## Power-Law Extrapolations",
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
                f"| {label} | {target} | {predict(phase_fits['elapsed_seconds'], target) / 3600:.3g} h | "
                f"{format_gib(predict(phase_fits['peak_rss_bytes'], target))} | "
                f"{format_gib(predict(phase_fits['storage_bytes'], target))} |"
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
            lines.append(f"| {file_type} | {target} | {format_gib(predict(fit, target))} |")

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
        print(f"Updated measured scaling values in {args.readme}")
    print(f"Wrote reports to {args.output_dir}")


if __name__ == "__main__":
    main()
