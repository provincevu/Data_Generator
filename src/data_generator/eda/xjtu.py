"""Reproducible time- and frequency-domain EDA for XJTU-SY."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from ..ingestion.xjtu import DATASET_NAME

ANCHOR_FRACTIONS = tuple(index / 10 for index in range(11))
SPECTRAL_BANDS_HZ = ((0.0, 1_000.0), (1_000.0, 5_000.0), (5_000.0, 10_000.0), (10_000.0, 12_800.0))

TIME_SUMMARY_SCHEMA = pa.schema([
    ("dataset_name", pa.string()), ("experiment_id", pa.string()), ("bearing_id", pa.string()),
    ("measurement_index", pa.int64()), ("elapsed_time_sec", pa.float64()),
    ("rotational_speed_rpm", pa.float64()), ("radial_load_kn", pa.float64()),
    ("channel_id", pa.string()), ("channel_direction", pa.string()), ("sampling_rate_hz", pa.float64()),
    ("signal_length", pa.int64()), ("duration_sec", pa.float64()), ("mean", pa.float64()),
    ("std", pa.float64()), ("rms", pa.float64()), ("peak_abs", pa.float64()), ("peak_to_peak", pa.float64()),
    ("kurtosis", pa.float64()), ("crest_factor", pa.float64()), ("fault_element_raw", pa.string()),
    ("fault_elements", pa.list_(pa.string())), ("failure_observed", pa.bool_()),
])

FFT_SUMMARY_SCHEMA = pa.schema([
    ("dataset_name", pa.string()), ("experiment_id", pa.string()), ("bearing_id", pa.string()),
    ("channel_id", pa.string()), ("channel_direction", pa.string()), ("anchor_fraction", pa.float64()),
    ("anchor_percent", pa.int64()), ("selected_measurement_index", pa.int64()),
    ("selected_elapsed_time_sec", pa.float64()), ("sampling_rate_hz", pa.float64()), ("signal_length", pa.int64()),
    ("frequency_resolution_hz", pa.float64()), ("n_fft", pa.int64()), ("preprocessing", pa.string()),
    ("window", pa.string()), ("dominant_frequency_hz", pa.float64()), ("dominant_amplitude", pa.float64()),
    ("total_spectral_power", pa.float64()), ("band_power_0_1000_hz", pa.float64()),
    ("band_power_1000_5000_hz", pa.float64()), ("band_power_5000_10000_hz", pa.float64()),
    ("band_power_10000_12800_hz", pa.float64()), ("frequencies_hz", pa.list_(pa.float32())),
    ("magnitude", pa.list_(pa.float32())), ("fault_element_raw", pa.string()),
    ("fault_elements", pa.list_(pa.string())), ("failure_observed", pa.bool_()),
])


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["dataset_name"], row["experiment_id"], row["bearing_id"]


def _load_trajectory_metadata(path: Path) -> dict[tuple[str, str, str], dict[str, Any]]:
    return {_key(row): row for row in pq.read_table(path).to_pylist()}


def _load_anchor_targets(path: Path) -> tuple[dict[tuple[str, str, str], dict[int, list[tuple[float, int]]]], dict[str, Any]]:
    indices: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    for row in pq.read_table(path, columns=["experiment_id", "bearing_id", "measurement_index", "parse_status"]).to_pylist():
        if row["parse_status"] == "ok" and row["measurement_index"] is not None:
            indices[(DATASET_NAME, row["experiment_id"], row["bearing_id"])].add(int(row["measurement_index"]))
    targets: dict[tuple[str, str, str], dict[int, list[tuple[float, int]]]] = {}
    duplicates: dict[str, int] = {}
    for key, values in indices.items():
        ordered = sorted(values)
        selected: dict[int, list[tuple[float, int]]] = defaultdict(list)
        for fraction in ANCHOR_FRACTIONS:
            position = int(np.floor(fraction * (len(ordered) - 1) + 0.5))
            selected[ordered[position]].append((fraction, round(fraction * 100)))
        targets[key] = dict(selected)
        duplicates["|".join(key)] = sum(max(0, len(item) - 1) for item in selected.values())
    return targets, {
        "trajectory_count": len(targets),
        "duplicate_anchor_count_by_trajectory": duplicates,
        "total_duplicate_anchor_count": sum(duplicates.values()),
    }


def _signal_metrics(signal: np.ndarray) -> dict[str, float]:
    """Compute waveform statistics using population moments over one snapshot."""
    values = np.asarray(signal, dtype=np.float64)
    mean = float(np.mean(values))
    centered = values - mean
    variance = float(np.mean(np.square(centered)))
    std = float(np.sqrt(variance))
    rms = float(np.sqrt(np.mean(np.square(values))))
    peak_abs = float(np.max(np.abs(values)))
    kurtosis_value = (
        float(np.mean(np.power(centered, 4)) / (variance**2))
        if values.size > 3 and variance > 0.0
        else float("nan")
    )
    return {
        "mean": mean,
        "std": std,
        "rms": rms,
        "peak_abs": peak_abs,
        "peak_to_peak": float(np.ptp(values)),
        "kurtosis": kurtosis_value,
        "crest_factor": peak_abs / rms if rms > 0 else float("nan"),
    }


def _fft_summary(signal: np.ndarray, sampling_rate_hz: float) -> dict[str, Any]:
    values = np.asarray(signal, dtype=np.float64)
    n_fft = int(values.size)
    if n_fft < 2:
        raise ValueError("FFT requires at least two samples")
    window = np.hanning(n_fft)
    centered = values - np.mean(values)
    frequencies = np.fft.rfftfreq(n_fft, d=1.0 / sampling_rate_hz)
    magnitude = np.abs(np.fft.rfft(centered * window)) / float(np.sum(window)) * 2.0
    magnitude[0] /= 2.0
    if n_fft % 2 == 0:
        magnitude[-1] /= 2.0
    dominant = int(np.argmax(magnitude[1:]) + 1)
    power = np.square(magnitude)
    bands = []
    for low, high in SPECTRAL_BANDS_HZ:
        mask = (frequencies >= low) & ((frequencies <= high) if high >= sampling_rate_hz / 2 else (frequencies < high))
        bands.append(float(np.sum(power[mask])))
    return {
        "frequency_resolution_hz": float(sampling_rate_hz / n_fft), "n_fft": n_fft,
        "preprocessing": "mean_centered", "window": "hann",
        "dominant_frequency_hz": float(frequencies[dominant]), "dominant_amplitude": float(magnitude[dominant]),
        "total_spectral_power": float(np.sum(power)), "band_power_0_1000_hz": bands[0],
        "band_power_1000_5000_hz": bands[1], "band_power_5000_10000_hz": bands[2],
        "band_power_10000_12800_hz": bands[3], "frequencies_hz": frequencies.astype(np.float32).tolist(),
        "magnitude": magnitude.astype(np.float32).tolist(),
    }


def _time_row(row: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    signal = np.asarray(row["vibration_signal"], dtype=np.float64)
    return {
        "dataset_name": row["dataset_name"], "experiment_id": row["experiment_id"], "bearing_id": row["bearing_id"],
        "measurement_index": row["measurement_index"], "elapsed_time_sec": row["elapsed_time_sec"],
        "rotational_speed_rpm": row["rotational_speed_rpm"], "radial_load_kn": row["radial_load_kn"],
        "channel_id": row["channel_id"], "channel_direction": row["channel_direction"],
        "sampling_rate_hz": row["sampling_rate_hz"], "signal_length": len(signal),
        "duration_sec": len(signal) / float(row["sampling_rate_hz"]), **_signal_metrics(signal),
        "fault_element_raw": metadata["fault_element_raw"], "fault_elements": metadata["fault_elements"],
        "failure_observed": metadata["failure_observed"],
    }


def _fft_rows(row: dict[str, Any], metadata: dict[str, Any], anchors: Iterable[tuple[float, int]]) -> list[dict[str, Any]]:
    signal = np.asarray(row["vibration_signal"], dtype=np.float64)
    summary = _fft_summary(signal, float(row["sampling_rate_hz"]))
    return [{
        "dataset_name": row["dataset_name"], "experiment_id": row["experiment_id"], "bearing_id": row["bearing_id"],
        "channel_id": row["channel_id"], "channel_direction": row["channel_direction"],
        "anchor_fraction": fraction, "anchor_percent": percent,
        "selected_measurement_index": row["measurement_index"], "selected_elapsed_time_sec": row["elapsed_time_sec"],
        "sampling_rate_hz": row["sampling_rate_hz"], "signal_length": len(signal), **summary,
        "fault_element_raw": metadata["fault_element_raw"], "fault_elements": metadata["fault_elements"],
        "failure_observed": metadata["failure_observed"],
    } for fraction, percent in anchors]


def _write_batch(writer: pq.ParquetWriter | None, path: Path, rows: list[dict[str, Any]], schema: pa.Schema) -> pq.ParquetWriter:
    if writer is None:
        writer = pq.ParquetWriter(path, schema, compression="zstd")
    writer.write_table(pa.Table.from_pylist(rows, schema=schema))
    return writer


def _plot_eda(output_dir: Path, time_path: Path, fft_path: Path, metadata_path: Path) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = pq.read_table(time_path, columns=["experiment_id", "bearing_id", "channel_id", "elapsed_time_sec", "rms", "peak_abs"]).to_pylist()
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in summary:
        grouped[(row["experiment_id"], row["bearing_id"], row["channel_id"])].append(row)
    keys = sorted({(key[0], key[1]) for key in grouped})
    for metric, filename, ylabel in (("rms", "lifecycle_rms.png", "RMS"), ("peak_abs", "lifecycle_peak_abs.png", "Peak absolute value")):
        figure, axes = plt.subplots(3, 5, figsize=(18, 10))
        for axis, (experiment, bearing) in zip(axes.flat, keys):
            for channel, color in (("horizontal", "tab:blue"), ("vertical", "tab:orange")):
                rows = sorted(grouped[(experiment, bearing, channel)], key=lambda item: item["elapsed_time_sec"])
                axis.plot([item["elapsed_time_sec"] / 60 for item in rows], [item[metric] for item in rows], color=color, linewidth=0.8, label=channel)
            axis.set_title(f"{experiment} / {bearing}"); axis.set_xlabel("Elapsed time (min)"); axis.set_ylabel(ylabel); axis.grid(alpha=0.25)
        handles, labels = axes.flat[0].get_legend_handles_labels(); figure.legend(handles, labels, loc="upper center", ncol=2)
        figure.tight_layout(rect=(0, 0, 1, 0.96)); figure.savefig(output_dir / filename, dpi=160); plt.close(figure)
    fft = pq.read_table(fft_path, columns=["experiment_id", "channel_id", "anchor_percent", "frequencies_hz", "magnitude"]).to_pylist()
    fft_grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in fft:
        fft_grouped[(row["experiment_id"], row["channel_id"], row["anchor_percent"])].append(row)
    figure, axes = plt.subplots(3, 2, figsize=(15, 12), sharex=True, sharey=True)
    colors = plt.cm.viridis(np.linspace(0.05, 0.95, len(ANCHOR_FRACTIONS)))
    panels = [(experiment, channel) for experiment in ("condition_1", "condition_2", "condition_3") for channel in ("horizontal", "vertical")]
    for axis, (experiment, channel) in zip(axes.flat, panels):
        for color, fraction in zip(colors, ANCHOR_FRACTIONS):
            rows = fft_grouped[(experiment, channel, round(fraction * 100))]
            if not rows:
                continue
            grid = np.linspace(0, min(max(row["frequencies_hz"]) for row in rows), 512)
            spectra = [np.interp(grid, row["frequencies_hz"], row["magnitude"]) for row in rows]
            axis.plot(grid, 20 * np.log10(np.median(np.asarray(spectra), axis=0) + 1e-12), color=color, linewidth=0.8, label=f"{int(fraction * 100)}%")
        axis.set_title(f"{experiment} / {channel}"); axis.set_xlabel("Frequency (Hz)"); axis.set_ylabel("Median magnitude (dB)"); axis.grid(alpha=0.25)
    axes.flat[-1].legend(loc="upper right", ncol=2, fontsize="small"); figure.tight_layout(); figure.savefig(output_dir / "fft_anchor_spectra.png", dpi=160); plt.close(figure)
    metadata = pq.read_table(metadata_path, columns=["experiment_id", "bearing_id", "reported_lifetime_min"]).to_pylist()
    figure, axis = plt.subplots(figsize=(14, 6)); axis.bar([f"{row['experiment_id']} / {row['bearing_id']}" for row in metadata], [row["reported_lifetime_min"] for row in metadata]); axis.set_ylabel("Reported lifetime (min)"); axis.tick_params(axis="x", rotation=60); figure.tight_layout(); figure.savefig(output_dir / "reported_lifetime_by_bearing.png", dpi=160); plt.close(figure)
    return ["lifecycle_rms.png", "lifecycle_peak_abs.png", "fft_anchor_spectra.png", "reported_lifetime_by_bearing.png"]


def run_xjtu_eda(observations_path: str | Path, manifest_path: str | Path, trajectory_metadata_path: str | Path, output_dir: str | Path, *, plot_dir: str | Path | None = None, make_plots: bool = True) -> dict[str, Any]:
    """Generate time-domain summaries for all observations and 11-anchor FFT summaries."""
    observations_path, manifest_path, trajectory_metadata_path, output_dir = [Path(path).resolve() for path in (observations_path, manifest_path, trajectory_metadata_path, output_dir)]
    for path, label in ((observations_path, "observations"), (manifest_path, "manifest"), (trajectory_metadata_path, "trajectory metadata")):
        if not path.is_file():
            raise FileNotFoundError(f"{label} do not exist: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = _load_trajectory_metadata(trajectory_metadata_path)
    targets, anchor_report = _load_anchor_targets(manifest_path)
    parquet = pq.ParquetFile(observations_path)
    time_path, fft_path = output_dir / "xjtu_signal_summary.parquet", output_dir / "xjtu_fft_summary.parquet"
    time_writer = fft_writer = None
    time_count = fft_count = 0
    trajectory_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    columns = ["dataset_name", "experiment_id", "bearing_id", "measurement_index", "elapsed_time_sec", "rotational_speed_rpm", "radial_load_kn", "channel_id", "channel_direction", "sampling_rate_hz", "signal_length", "vibration_signal"]
    for batch in parquet.iter_batches(columns=columns, batch_size=16):
        rows = batch.to_pylist(); output = []
        for row in rows:
            key = _key(row)
            if key not in metadata:
                raise ValueError(f"observation has no trajectory metadata: {key}")
            output.append(_time_row(row, metadata[key])); trajectory_counts[key] += 1
        if output:
            time_writer = _write_batch(time_writer, time_path, output, TIME_SUMMARY_SCHEMA); time_count += len(output)
    if time_writer is None:
        pq.write_table(pa.Table.from_pylist([], schema=TIME_SUMMARY_SCHEMA), time_path)
    else:
        time_writer.close()
    fft_columns = ["dataset_name", "experiment_id", "bearing_id", "measurement_index", "elapsed_time_sec", "channel_id", "channel_direction", "sampling_rate_hz", "signal_length", "vibration_signal"]
    for batch in parquet.iter_batches(columns=fft_columns, batch_size=8):
        output = []
        for row in batch.to_pylist():
            key = _key(row); anchors = targets.get(key, {}).get(int(row["measurement_index"]), [])
            if anchors:
                output.extend(_fft_rows(row, metadata[key], anchors))
        if output:
            fft_writer = _write_batch(fft_writer, fft_path, output, FFT_SUMMARY_SCHEMA); fft_count += len(output)
    if fft_writer is None:
        pq.write_table(pa.Table.from_pylist([], schema=FFT_SUMMARY_SCHEMA), fft_path)
    else:
        fft_writer.close()
    plots = _plot_eda(Path(plot_dir).resolve() if plot_dir else output_dir.parents[2] / "artifacts" / "xjtu_eda", time_path, fft_path, trajectory_metadata_path) if make_plots else []
    report = {
        "schema_version": "1.0", "dataset_name": DATASET_NAME, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {"observations": str(observations_path), "manifest": str(manifest_path), "trajectory_metadata": str(trajectory_metadata_path)},
        "configuration": {"anchor_fractions": list(ANCHOR_FRACTIONS), "fft_preprocessing": "subtract waveform mean", "fft_window": "Hann", "spectral_bands_hz": [list(band) for band in SPECTRAL_BANDS_HZ], "time_domain_metrics": {"std": "sqrt(E[(x - mean)^2])", "kurtosis": "E[(x - mean)^4] / std^4", "crest_factor": "peak_abs / rms"}, "time_summary_scope": "all observations and channels", "fft_scope": "selected observations and channels at 11 normalized anchors"},
        "summary": {"observation_summary_rows": time_count, "fft_summary_rows": fft_count, "trajectory_count": len(trajectory_counts), "plot_count": len(plots)},
        "anchor_selection": anchor_report,
        "output_files": ["xjtu_signal_summary.parquet", "xjtu_fft_summary.parquet", "xjtu_eda_report.json"], "plot_files": plots,
    }
    (output_dir / "xjtu_eda_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
