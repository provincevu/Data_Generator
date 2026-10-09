"""Command-line entry points for data ingestion, features, EDA, sampling, and baselines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .baselines.causal import run_baseline_evaluation
from .eda.xjtu import run_xjtu_eda
from .features.xjtu import run_xjtu_features
from .ingestion.metadata import build_xjtu_metadata
from .ingestion.xjtu import parse_xjtu
from .sampling.causal import sample_causal_manifest


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
    sampler = subparsers.add_parser("sample-xjtu", help="sample causal XJTU-SY manifests")
    sampler.add_argument("--project-root", type=Path, default=Path.cwd())
    sampler.add_argument("--snapshot-features", type=Path)
    sampler.add_argument("--output", type=Path)
    sampler.add_argument("--split", choices=("train", "validation", "test"), required=True)
    sampler.add_argument("--seed", type=int, required=True)
    sampler.add_argument("--epoch", type=int)
    sampler.add_argument("--anchors-per-trajectory", type=int, required=True)
    sampler.add_argument("--context-regime", choices=("main", "short_robustness"), default="main")
    sampler.add_argument("--sparse-regime", choices=("dense", "sparse_10", "sparse_5", "sparse_1"), default="dense")
    sampler.add_argument("--full-remaining-lifecycle", action="store_true")
    baseline = subparsers.add_parser("baseline-xjtu", help="fit and evaluate causal baseline models")
    baseline.add_argument("--project-root", type=Path, default=Path.cwd())
    baseline.add_argument("--snapshot-features", type=Path)
    baseline.add_argument("--train-manifest", type=Path, required=True)
    baseline.add_argument("--eval-manifest", type=Path, nargs="+", required=True)
    baseline.add_argument("--output-dir", type=Path)
    baseline.add_argument("--random-state", type=int, default=0)
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
    if args.command == "sample-xjtu":
        snapshot_features = args.snapshot_features or project_root / "data/interim/xjtu/xjtu_snapshot_features.parquet"
        output = args.output or project_root / "data/interim/xjtu" / f"xjtu_sample_manifest_{args.split}.parquet"
        report = sample_causal_manifest(
            snapshot_features,
            output,
            split=args.split,
            seed=args.seed,
            anchors_per_trajectory=args.anchors_per_trajectory,
            context_regime=args.context_regime,
            sparse_regime=args.sparse_regime,
            epoch=args.epoch,
            full_remaining_lifecycle=args.full_remaining_lifecycle,
        )
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        return 0
    if args.command == "baseline-xjtu":
        snapshot_features = args.snapshot_features or project_root / "data/interim/xjtu/xjtu_snapshot_features.parquet"
        output_dir = args.output_dir or project_root / "data/interim/xjtu/baselines"
        report = run_baseline_evaluation(
            snapshot_features,
            args.train_manifest,
            args.eval_manifest,
            output_dir,
            random_state=args.random_state,
        )
        print(json.dumps({
            "status": report["status"],
            "models": report["models"],
            "metrics_path": report["metrics_path"],
            "training_samples": report["training_samples"],
            "evaluation_manifests": report["evaluation_manifests"],
        }, ensure_ascii=False, indent=2))
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

