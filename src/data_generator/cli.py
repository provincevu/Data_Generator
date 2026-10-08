"""Command-line entry points for data ingestion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

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
    metadata = subparsers.add_parser(
        "build-xjtu-metadata", help="normalize XJTU-SY metadata"
    )
    metadata.add_argument("--project-root", type=Path, default=Path.cwd())
    metadata.add_argument("--metadata-config", type=Path)
    metadata.add_argument("--manifest", type=Path)
    metadata.add_argument("--output-dir", type=Path)
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())