"""Command-line entry points for data ingestion, features, and EDA."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .eda.xjtu import run_xjtu_eda
from .features.xjtu import run_xjtu_features
from .ingestion.metadata import build_xjtu_metadata
from .ingestion.xjtu import parse_xjtu


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="data-generator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    xjtu = subparsers.add_parser("parse-xjtu", help="parse XJTU-SY raw CSV files")
    xjtu.add_argument("--project-root", type=Path, default=Path.cwd())
    xjtu.add_argument("--raw-root", type=Path)
    xjtu.add_argument("--output-dir", type=Path)
    xjtu.add_argument("--allow-errors", action="store_true")
    metadata = subparsers.add_parser("build-xjtu-metadata", help="normalize XJTU-SY metadata")
    metadata.add_argument("--project-root", type=Path, default=Path.cwd())
    metadata.add_argument("--metadata-config", type=Path)
    metadata.add_argument("--manifest", type=Path)
    metadata.add_argument("--output-dir", type=Path)
    features = subparsers.add_parser("features-xjtu", help="build fixed-dimensional XJTU-SY features")
    features.add_argument("--project-root", type=Path, default=Path.cwd())
    features.add_argument("--observations", type=Path)
    features.add_argument("--output-dir", type=Path)
    eda = subparsers.add_parser("eda-xjtu", help="run XJTU-SY exploratory data analysis")
    eda.add_argument("--project-root", type=Path, default=Path.cwd())
    eda.add_argument("--observations", type=Path)
    eda.add_argument("--manifest", type=Path)
    eda.add_argument("--trajectory-metadata", type=Path)
    eda.add_argument("--output-dir", type=Path)
    eda.add_argument("--plot-dir", type=Path)
    eda.add_argument("--bearing-geometry", type=Path)
    eda.add_argument("--no-plots", action="store_true")
    eda.add_argument("--force-recompute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = args.project_root.resolve()
    if args.command == "parse-xjtu":
        raw_root = args.raw_root or project_root / "data/raw/XJTU-SY_Bearing_Datasets/Data/XJTU-SY_Bearing_Datasets"
        output_dir = args.output_dir or project_root / "data/interim/xjtu"
        report = parse_xjtu(raw_root, output_dir)
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        if report["summary"]["files_with_errors"] and not args.allow_errors:
            return 1
        return 0
    if args.command == "build-xjtu-metadata":
        metadata_config = args.metadata_config or project_root / "configs/xjtu_trajectory_metadata.csv"
        manifest = args.manifest or project_root / "data/interim/xjtu/xjtu_source_manifest.parquet"
        output_dir = args.output_dir or project_root / "data/interim/xjtu"
        report = build_xjtu_metadata(metadata_config, manifest, output_dir)
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return 0
    if args.command == "features-xjtu":
        observations = args.observations or project_root / "data/interim/xjtu/xjtu_observations.parquet"
        output_dir = args.output_dir or project_root / "data/interim/xjtu"
        report = run_xjtu_features(observations, output_dir)
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return 0
    if args.command == "eda-xjtu":
        observations = args.observations or project_root / "data/interim/xjtu/xjtu_observations.parquet"
        manifest = args.manifest or project_root / "data/interim/xjtu/xjtu_source_manifest.parquet"
        trajectory_metadata = args.trajectory_metadata or project_root / "data/interim/xjtu/xjtu_trajectory_metadata.parquet"
        output_dir = args.output_dir or project_root / "data/interim/xjtu"
        report = run_xjtu_eda(
            observations,
            manifest,
            trajectory_metadata,
            output_dir,
            plot_dir=args.plot_dir,
            bearing_geometry_path=args.bearing_geometry,
            make_plots=not args.no_plots,
            force_recompute=args.force_recompute,
        )
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
