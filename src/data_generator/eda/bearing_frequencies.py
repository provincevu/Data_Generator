"""Bearing characteristic-frequency calculations for the XJTU-SY EDA."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class BearingGeometry:
    """Geometry required by BPFO, BPFI, BSF, and FTF formulas."""

    bearing_model: str
    number_of_rolling_elements: int
    rolling_element_diameter_mm: float
    pitch_diameter_mm: float
    contact_angle_deg: float = 0.0
    source: str | None = None


def load_bearing_geometry(path: str | Path | None) -> BearingGeometry | None:
    """Load optional geometry; return None when no configuration is supplied."""
    if path is None:
        return None
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"bearing geometry config does not exist: {config_path}")
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    required = (
        "bearing_model",
        "number_of_rolling_elements",
        "rolling_element_diameter_mm",
        "pitch_diameter_mm",
    )
    missing = [name for name in required if raw.get(name) is None]
    if missing:
        raise ValueError(
            "bearing geometry config is incomplete; missing values: "
            + ", ".join(missing)
        )
    geometry = BearingGeometry(
        bearing_model=str(raw["bearing_model"]),
        number_of_rolling_elements=int(raw["number_of_rolling_elements"]),
        rolling_element_diameter_mm=float(raw["rolling_element_diameter_mm"]),
        pitch_diameter_mm=float(raw["pitch_diameter_mm"]),
        contact_angle_deg=float(raw.get("contact_angle_deg", 0.0)),
        source=str(raw["source"]) if raw.get("source") is not None else None,
    )
    if geometry.number_of_rolling_elements <= 0:
        raise ValueError("number_of_rolling_elements must be positive")
    if geometry.rolling_element_diameter_mm <= 0 or geometry.pitch_diameter_mm <= 0:
        raise ValueError("bearing diameters must be positive")
    if geometry.pitch_diameter_mm <= geometry.rolling_element_diameter_mm:
        raise ValueError("pitch_diameter_mm must exceed rolling_element_diameter_mm")
    if not 0.0 <= geometry.contact_angle_deg < 90.0:
        raise ValueError("contact_angle_deg must be in [0, 90)")
    return geometry


def characteristic_frequencies(
    rotational_speed_rpm: float,
    geometry: BearingGeometry | None,
) -> dict[str, float | None]:
    """Return shaft frequency and bearing fault frequencies in Hz."""
    shaft_frequency_hz = float(rotational_speed_rpm) / 60.0
    if geometry is None:
        return {
            "shaft_frequency_hz": shaft_frequency_hz,
            "bpfo_hz": None,
            "bpfi_hz": None,
            "bsf_hz": None,
            "ftf_hz": None,
        }
    ratio = geometry.rolling_element_diameter_mm / geometry.pitch_diameter_mm
    cosine = math.cos(math.radians(geometry.contact_angle_deg))
    n_elements = geometry.number_of_rolling_elements
    return {
        "shaft_frequency_hz": shaft_frequency_hz,
        "bpfo_hz": n_elements / 2.0 * shaft_frequency_hz * (1.0 - ratio * cosine),
        "bpfi_hz": n_elements / 2.0 * shaft_frequency_hz * (1.0 + ratio * cosine),
        "bsf_hz": geometry.pitch_diameter_mm / (2.0 * geometry.rolling_element_diameter_mm)
        * shaft_frequency_hz
        * (1.0 - (ratio * cosine) ** 2),
        "ftf_hz": 0.5 * shaft_frequency_hz * (1.0 - ratio * cosine),
    }
