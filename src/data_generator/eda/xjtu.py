"""Reproducible time- and frequency-domain EDA for XJTU-SY."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .bearing_frequencies import (
    BearingGeometry,
    characteristic_frequencies,
    load_bearing_geometry,
)
from ..ingestion.xjtu import DATASET_NAME

ANCHOR_FRACTIONS = tuple(index / 10 for index in range(11))
SPECTRAL_BANDS_HZ = ((0.0, 1_000.0), (1_000.0, 5_000.0), (5_000.0, 10_000.0), (10_000.0, 12_800.0))
TIME_CACHE_VERSION = "2"
FFT_CACHE_VERSION = "2"
PLOT_CACHE_VERSION = "4"
EXPECTED_PLOT_FILES = (
    "lifecycle_rms.png",
    "lifecycle_peak_abs.png",
    "lifecycle_std.png",
    "lifecycle_kurtosis.png",
    "lifecycle_crest_factor.png",
    "fft_anchor_spectra.png",
    "reported_lifetime_by_bearing.png",
)

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
    ("selected_elapsed_time_sec", pa.float64()), ("rotational_speed_rpm", pa.float64()),
    ("sampling_rate_hz", pa.float64()), ("signal_length", pa.int64()),
    ("frequency_resolution_hz", pa.float64()), ("n_fft", pa.int64()), ("preprocessing", pa.string()),
    ("window", pa.string()), ("dominant_frequency_hz", pa.float64()), ("dominant_amplitude", pa.float64()),
    ("shaft_frequency_hz", pa.float64()), ("bpfo_hz", pa.float64()), ("bpfi_hz", pa.float64()),
    ("bsf_hz", pa.float64()), ("ftf_hz", pa.float64()),
    ("characteristic_frequency_status", pa.string()), ("bearing_geometry_source", pa.string()),
    ("total_spectral_power", pa.float64()), ("band_power_0_1000_hz", pa.float64()),
    ("band_power_1000_5000_hz", pa.float64()), ("band_power_5000_10000_hz", pa.float64()),
    ("band_power_10000_12800_hz", pa.float64()), ("frequencies_hz", pa.list_(pa.float32())),
    ("magnitude", pa.list_(pa.float32())), ("fault_element_raw", pa.string()),
    ("fault_elements", pa.list_(pa.string())), ("failure_observed", pa.bool_()),
])


def _file_signature(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _cache_key(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_cache(path: Path) -> dict[str, Any]:
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return cache if cache.get("schema_version") == "1.0" else {}


def _cache_entry_valid(
    cache: dict[str, Any],
    name: str,
    key: str,
    output_paths: tuple[Path, ...],
) -> bool:
    entry = cache.get("entries", {}).get(name, {})
    return entry.get("key") == key and all(path.is_file() for path in output_paths)


def _cache_entry(key: str, output_paths: tuple[Path, ...]) -> dict[str, Any]:
    return {"key": key, "outputs": [path.name for path in output_paths]}

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


def _fft_rows(
    row: dict[str, Any],
    metadata: dict[str, Any],
    anchors: Iterable[tuple[float, int]],
    geometry: BearingGeometry | None,
) -> list[dict[str, Any]]:
    signal = np.asarray(row["vibration_signal"], dtype=np.float64)
    summary = _fft_summary(signal, float(row["sampling_rate_hz"]))
    characteristic = characteristic_frequencies(float(row["rotational_speed_rpm"]), geometry)
    return [{
        "dataset_name": row["dataset_name"], "experiment_id": row["experiment_id"], "bearing_id": row["bearing_id"],
        "channel_id": row["channel_id"], "channel_direction": row["channel_direction"],
        "anchor_fraction": fraction, "anchor_percent": percent,
        "selected_measurement_index": row["measurement_index"], "selected_elapsed_time_sec": row["elapsed_time_sec"],
        "rotational_speed_rpm": row["rotational_speed_rpm"],
        "sampling_rate_hz": row["sampling_rate_hz"], "signal_length": len(signal), **summary,
        **characteristic,
        "characteristic_frequency_status": (
            "configured" if geometry is not None else "geometry_not_configured"
        ),
        "bearing_geometry_source": geometry.source if geometry is not None else None,
        "fault_element_raw": metadata["fault_element_raw"], "fault_elements": metadata["fault_elements"],
        "failure_observed": metadata["failure_observed"],
    } for fraction, percent in anchors]


def _write_batch(writer: pq.ParquetWriter | None, path: Path, rows: list[dict[str, Any]], schema: pa.Schema) -> pq.ParquetWriter:
    if writer is None:
        writer = pq.ParquetWriter(path, schema, compression="zstd")
    writer.write_table(pa.Table.from_pylist(rows, schema=schema))
    return writer


def _plot_eda(
    output_dir: Path,
    time_path: Path,
    fft_path: Path,
    metadata_path: Path,
) -> list[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = pq.read_table(
        time_path,
        columns=[
            "experiment_id",
            "bearing_id",
            "channel_id",
            "elapsed_time_sec",
            "rms",
            "peak_abs",
            "std",
            "kurtosis",
            "crest_factor",
        ],
    ).to_pylist()
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in summary:
        grouped[(row["experiment_id"], row["bearing_id"], row["channel_id"])].append(row)

    condition_labels = {
        "condition_1": "Điều kiện 1",
        "condition_2": "Điều kiện 2",
        "condition_3": "Điều kiện 3",
    }
    channel_labels = {"horizontal": "kênh ngang", "vertical": "kênh đứng"}
    keys = sorted({(key[0], key[1]) for key in grouped})
    metric_specs = (
        ("rms", "lifecycle_rms.png", "RMS (mức rung hiệu dụng)"),
        ("peak_abs", "lifecycle_peak_abs.png", "Biên độ tuyệt đối lớn nhất"),
        ("std", "lifecycle_std.png", "Độ lệch chuẩn"),
        ("kurtosis", "lifecycle_kurtosis.png", "Kurtosis (độ nhọn)"),
        ("crest_factor", "lifecycle_crest_factor.png", "Crest factor (hệ số đỉnh)"),
    )
    for metric, filename, ylabel in metric_specs:
        figure, axes = plt.subplots(3, 5, figsize=(18, 10))
        for axis, (experiment, bearing) in zip(axes.flat, keys):
            for channel, color in (("horizontal", "tab:blue"), ("vertical", "tab:orange")):
                rows = sorted(
                    grouped[(experiment, bearing, channel)],
                    key=lambda item: item["elapsed_time_sec"],
                )
                axis.plot(
                    [item["elapsed_time_sec"] / 60 for item in rows],
                    [item[metric] for item in rows],
                    color=color,
                    linewidth=0.8,
                    label=channel_labels[channel],
                )
            axis.set_title(f"{condition_labels[experiment]} / {bearing}")
            axis.set_xlabel("Thời gian vận hành (phút)")
            axis.set_ylabel(ylabel)
            axis.grid(alpha=0.25)
        handles, labels = axes.flat[0].get_legend_handles_labels()
        figure.legend(handles, labels, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.90))
        figure.suptitle(
            f"XJTU-SY — {ylabel} theo vòng đời\n"
            "Mỗi ô là một vòng bi; xanh: kênh ngang, cam: kênh đứng",
        )
        figure.tight_layout(rect=(0, 0, 1, 0.84))
        figure.savefig(output_dir / filename, dpi=160)
        plt.close(figure)

    fft = pq.read_table(
        fft_path,
        columns=[
            "experiment_id",
            "channel_id",
            "anchor_percent",
            "frequencies_hz",
            "magnitude",
        ],
    ).to_pylist()
    fft_grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in fft:
        fft_grouped[(row["experiment_id"], row["channel_id"], row["anchor_percent"])].append(row)

    figure, axes = plt.subplots(3, 2, figsize=(15, 12), sharex=True, sharey=True)
    colors = plt.cm.viridis(np.linspace(0.05, 0.95, len(ANCHOR_FRACTIONS)))
    panels = [
        (experiment, channel)
        for experiment in ("condition_1", "condition_2", "condition_3")
        for channel in ("horizontal", "vertical")
    ]
    for axis, (experiment, channel) in zip(axes.flat, panels):
        for color, fraction in zip(colors, ANCHOR_FRACTIONS):
            rows = fft_grouped[(experiment, channel, round(fraction * 100))]
            if not rows:
                continue
            grid = np.linspace(0, min(max(row["frequencies_hz"]) for row in rows), 512)
            spectra = [
                np.interp(grid, row["frequencies_hz"], row["magnitude"])
                for row in rows
            ]
            axis.plot(
                grid,
                20 * np.log10(np.median(np.asarray(spectra), axis=0) + 1e-12),
                color=color,
                linewidth=0.8,
                label=f"{round(fraction * 100)}%",
            )
        axis.set_title(f"{condition_labels[experiment]} / {channel_labels[channel]}")
        axis.set_xlabel("Tần số (Hz)")
        axis.set_ylabel("Biên độ phổ trung vị (dB)")
        axis.grid(alpha=0.25)
    axes.flat[-1].legend(loc="upper right", ncol=2, fontsize="small")
    figure.suptitle(
        "XJTU-SY — Diễn biến phổ tần số theo 11 mốc vòng đời\n"
        "Mỗi màu là một mốc phần trăm; phổ là trung vị của 5 vòng bi trong cùng điều kiện",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.84))
    figure.savefig(output_dir / "fft_anchor_spectra.png", dpi=160)
    plt.close(figure)

    metadata = pq.read_table(
        metadata_path,
        columns=["experiment_id", "bearing_id", "reported_lifetime_min"],
    ).to_pylist()
    labels = [
        f"{condition_labels[row['experiment_id']]} / {row['bearing_id']}"
        for row in metadata
    ]
    figure, axis = plt.subplots(figsize=(14, 6))
    axis.bar(labels, [row["reported_lifetime_min"] for row in metadata])
    axis.set_title("Tuổi thọ được công bố của các trajectory XJTU-SY")
    axis.set_ylabel("Tuổi thọ theo tài liệu (phút)")
    axis.set_xlabel("Điều kiện vận hành / vòng bi")
    axis.tick_params(axis="x", rotation=60)
    figure.tight_layout()
    figure.savefig(output_dir / "reported_lifetime_by_bearing.png", dpi=160)
    plt.close(figure)

    return list(EXPECTED_PLOT_FILES)


def run_xjtu_eda(
    observations_path: str | Path,
    manifest_path: str | Path,
    trajectory_metadata_path: str | Path,
    output_dir: str | Path,
    *,
    plot_dir: str | Path | None = None,
    bearing_geometry_path: str | Path | None = None,
    make_plots: bool = True,
    force_recompute: bool = False,
) -> dict[str, Any]:
    """Generate cached summaries and Vietnamese plots for XJTU-SY."""
    observations_path, manifest_path, trajectory_metadata_path, output_dir = [
        Path(path).resolve()
        for path in (observations_path, manifest_path, trajectory_metadata_path, output_dir)
    ]
    bearing_geometry_path = (
        Path(bearing_geometry_path).resolve()
        if bearing_geometry_path is not None
        else None
    )
    bearing_geometry = load_bearing_geometry(bearing_geometry_path)
    for path, label in (
        (observations_path, "observations"),
        (manifest_path, "manifest"),
        (trajectory_metadata_path, "trajectory metadata"),
    ):
        if not path.is_file():
            raise FileNotFoundError(f"{label} do not exist: {path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    time_path = output_dir / "xjtu_signal_summary.parquet"
    fft_path = output_dir / "xjtu_fft_summary.parquet"
    report_path = output_dir / "xjtu_eda_report.json"
    cache_path = output_dir / "xjtu_eda_cache.json"
    cache = _load_cache(cache_path)
    anchor_targets, anchor_report = _load_anchor_targets(manifest_path)
    input_signatures = {
        "observations": _file_signature(observations_path),
        "manifest": _file_signature(manifest_path),
        "trajectory_metadata": _file_signature(trajectory_metadata_path),
    }
    if bearing_geometry_path is not None:
        input_signatures["bearing_geometry"] = _file_signature(bearing_geometry_path)
    time_key = _cache_key(
        {
            "version": TIME_CACHE_VERSION,
            "observations": input_signatures["observations"],
            "trajectory_metadata": input_signatures["trajectory_metadata"],
            "metrics": {
                "std": "population",
                "kurtosis": "raw_pearson",
                "crest_factor": "peak_abs/rms",
            },
        }
    )
    fft_key = _cache_key(
        {
            "version": FFT_CACHE_VERSION,
            "observations": input_signatures["observations"],
            "manifest": input_signatures["manifest"],
            "trajectory_metadata": input_signatures["trajectory_metadata"],
            "bearing_geometry": input_signatures.get("bearing_geometry"),
            "anchor_fractions": list(ANCHOR_FRACTIONS),
            "preprocessing": "mean_centered_hann",
        }
    )
    time_cached = (
        not force_recompute
        and _cache_entry_valid(cache, "time_summary", time_key, (time_path,))
    )
    fft_cached = (
        not force_recompute
        and _cache_entry_valid(cache, "fft_summary", fft_key, (fft_path,))
    )
    metadata: dict[tuple[str, str, str], dict[str, Any]] | None = None
    time_count = 0
    fft_count = 0

    if not time_cached or not fft_cached:
        metadata = _load_trajectory_metadata(trajectory_metadata_path)

    if time_cached:
        time_count = pq.ParquetFile(time_path).metadata.num_rows
    else:
        time_writer: pq.ParquetWriter | None = None
        columns = [
            "dataset_name",
            "experiment_id",
            "bearing_id",
            "measurement_index",
            "elapsed_time_sec",
            "rotational_speed_rpm",
            "radial_load_kn",
            "channel_id",
            "channel_direction",
            "sampling_rate_hz",
            "signal_length",
            "vibration_signal",
        ]
        for batch in pq.ParquetFile(observations_path).iter_batches(
            columns=columns,
            batch_size=16,
        ):
            rows = batch.to_pylist()
            output = []
            for row in rows:
                key = _key(row)
                if key not in metadata:
                    raise ValueError(f"observation has no trajectory metadata: {key}")
                output.append(_time_row(row, metadata[key]))
            if output:
                time_writer = _write_batch(
                    time_writer,
                    time_path,
                    output,
                    TIME_SUMMARY_SCHEMA,
                )
                time_count += len(output)
        if time_writer is None:
            pq.write_table(pa.Table.from_pylist([], schema=TIME_SUMMARY_SCHEMA), time_path)
        else:
            time_writer.close()

    if fft_cached:
        fft_count = pq.ParquetFile(fft_path).metadata.num_rows
    else:
        fft_writer: pq.ParquetWriter | None = None
        fft_columns = [
            "dataset_name",
            "experiment_id",
            "bearing_id",
            "measurement_index",
            "elapsed_time_sec",
            "rotational_speed_rpm",
            "channel_id",
            "channel_direction",
            "sampling_rate_hz",
            "signal_length",
            "vibration_signal",
        ]
        for batch in pq.ParquetFile(observations_path).iter_batches(
            columns=fft_columns,
            batch_size=8,
        ):
            output = []
            for row in batch.to_pylist():
                key = _key(row)
                anchors = anchor_targets.get(key, {}).get(
                    int(row["measurement_index"]),
                    [],
                )
                if anchors:
                    output.extend(_fft_rows(row, metadata[key], anchors, bearing_geometry))
            if output:
                fft_writer = _write_batch(
                    fft_writer,
                    fft_path,
                    output,
                    FFT_SUMMARY_SCHEMA,
                )
                fft_count += len(output)
        if fft_writer is None:
            pq.write_table(pa.Table.from_pylist([], schema=FFT_SUMMARY_SCHEMA), fft_path)
        else:
            fft_writer.close()

    plot_dir = (
        Path(plot_dir).resolve()
        if plot_dir is not None
        else output_dir.parents[2] / "artifacts" / "xjtu_eda"
    )
    plot_key = _cache_key(
        {
            "version": PLOT_CACHE_VERSION,
            "time_summary": _file_signature(time_path),
            "fft_summary": _file_signature(fft_path),
            "trajectory_metadata": input_signatures["trajectory_metadata"],
            "labels": "Vietnamese",
        }
    )
    plot_cached = (
        make_plots
        and not force_recompute
        and _cache_entry_valid(
            cache,
            "plots",
            plot_key,
            tuple(plot_dir / name for name in EXPECTED_PLOT_FILES),
        )
    )
    if plot_cached:
        plots = list(EXPECTED_PLOT_FILES)
    elif make_plots:
        plots = _plot_eda(plot_dir, time_path, fft_path, trajectory_metadata_path)
    else:
        plots = []

    entries = {
        "time_summary": _cache_entry(time_key, (time_path,)),
        "fft_summary": _cache_entry(fft_key, (fft_path,)),
    }
    if plots == list(EXPECTED_PLOT_FILES):
        entries["plots"] = _cache_entry(
            plot_key,
            tuple(plot_dir / name for name in EXPECTED_PLOT_FILES),
        )
    report = {
        "schema_version": "1.0",
        "dataset_name": DATASET_NAME,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "observations": str(observations_path),
            "manifest": str(manifest_path),
            "trajectory_metadata": str(trajectory_metadata_path),
            "bearing_geometry": (
                str(bearing_geometry_path) if bearing_geometry_path is not None else None
            ),
        },
        "configuration": {
            "anchor_fractions": list(ANCHOR_FRACTIONS),
            "fft_preprocessing": "subtract waveform mean",
            "fft_window": "Hann",
            "spectral_bands_hz": [list(band) for band in SPECTRAL_BANDS_HZ],
            "time_domain_metrics": {
                "std": "sqrt(E[(x - mean)^2])",
                "kurtosis": "E[(x - mean)^4] / std^4",
                "crest_factor": "peak_abs / rms",
            },
            "time_summary_scope": "all observations and channels",
            "fft_scope": "selected observations and channels at 11 normalized anchors",
            "bearing_characteristic_frequencies": {
                "status": (
                    "configured" if bearing_geometry is not None else "geometry_not_configured"
                ),
                "geometry_config": (
                    str(bearing_geometry_path) if bearing_geometry_path is not None else None
                ),
                "formulas": {
                    "bpfo_hz": "N/2 * fr * (1 - (d/D) * cos(theta))",
                    "bpfi_hz": "N/2 * fr * (1 + (d/D) * cos(theta))",
                    "bsf_hz": "D/(2*d) * fr * (1 - ((d/D) * cos(theta))^2)",
                    "ftf_hz": "1/2 * fr * (1 - (d/D) * cos(theta))",
                },
                "required_geometry_fields": [
                    "bearing_model",
                    "number_of_rolling_elements",
                    "rolling_element_diameter_mm",
                    "pitch_diameter_mm",
                    "contact_angle_deg",
                ],
            },
        },
        "summary": {
            "observation_summary_rows": time_count,
            "fft_summary_rows": fft_count,
            "trajectory_count": anchor_report["trajectory_count"],
            "plot_count": len(plots),
        },
        "cache": {
            "path": str(cache_path),
            "force_recompute": force_recompute,
            "used": {
                "time_summary": time_cached,
                "fft_summary": fft_cached,
                "plots": plot_cached,
            },
        },
        "anchor_selection": anchor_report,
        "output_files": [
            "xjtu_signal_summary.parquet",
            "xjtu_fft_summary.parquet",
            "xjtu_eda_report.json",
            "xjtu_eda_cache.json",
        ],
        "plot_files": plots,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "generated_at_utc": report["generated_at_utc"],
                "entries": entries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report
