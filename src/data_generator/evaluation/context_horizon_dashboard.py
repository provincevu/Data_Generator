"""Sensitivity evaluation for context windows and future horizons.

Use prepare to create an index-only manifest, then evaluate to join model
predictions with the canonical snapshot feature table and write metrics plus a
small HTML dashboard. This track does not replace the main 20-record sampler.

Prediction parquet columns:
sample_id and predicted_features (or prediction_features), each [Q, 30].
Optional prediction_samples may be [S, Q, 30] for interval metrics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

CONTEXT_LENGTHS = (30, 40, 50, 60)
RATIOS = (0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00)
SPARSE = {"dense": 1.0, "sparse_10": 0.1, "sparse_5": 0.05, "sparse_1": 0.01}
FEATURE_SCHEMA = "xjtu_feature_v1"
D = 30
EVAL_SCHEMA = "xjtu_context_horizon_eval_v1"
METRICS_SCHEMA = "xjtu_context_horizon_metrics_v1"


def stable_int(*parts: Any) -> int:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode()
    # Keep seeds inside Arrow's signed int64 range when persisted in Parquet.
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % (2**63 - 1)


def sample_id(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:24]


def trajectory_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return str(row["dataset_name"]), str(row["experiment_id"]), str(row["bearing_id"])


def load_snapshot(path: Path):
    table = pq.read_table(path)
    required = {
        "dataset_name", "experiment_id", "bearing_id", "measurement_index",
        "elapsed_time_sec", "split", "feature_schema_version",
        "feature_dimension", "feature_vector", "feature_valid_mask",
    }
    missing = required - set(table.column_names)
    if missing:
        raise ValueError(f"snapshot table is missing columns: {sorted(missing)}")
    trajectories = defaultdict(list)
    index = {}
    for raw in table.to_pylist():
        if raw["feature_schema_version"] != FEATURE_SCHEMA:
            raise ValueError(f"unsupported feature schema: {raw['feature_schema_version']!r}")
        if int(raw["feature_dimension"]) != D:
            raise ValueError(f"expected feature dimension {D}")
        key = (*trajectory_key(raw), int(raw["measurement_index"]))
        if key in index:
            raise ValueError(f"duplicate snapshot key: {key}")
        vector = np.asarray(raw["feature_vector"], dtype=float)
        valid = np.asarray(raw["feature_valid_mask"], dtype=bool)
        if vector.shape != (D,) or valid.shape != (D,):
            raise ValueError(f"invalid feature vector or mask at {key}")
        row = {
            "dataset_name": str(raw["dataset_name"]),
            "experiment_id": str(raw["experiment_id"]),
            "bearing_id": str(raw["bearing_id"]),
            "measurement_index": int(raw["measurement_index"]),
            "elapsed_time_sec": float(raw["elapsed_time_sec"]),
            "split": str(raw["split"]),
            "feature_vector": vector,
            "feature_valid_mask": valid,
        }
        index[key] = row
        trajectories[trajectory_key(raw)].append(row)
    for rows in trajectories.values():
        rows.sort(key=lambda r: (r["elapsed_time_sec"], r["measurement_index"]))
    return dict(trajectories), index


def context_pool(rows, anchor_pos: int, max_records: int):
    anchor_time = rows[anchor_pos]["elapsed_time_sec"]
    lower = anchor_time - max_records * 60.0
    pool = [r for r in rows[:anchor_pos + 1] if lower <= r["elapsed_time_sec"] <= anchor_time]
    return pool[-max_records:]


def select_context(pool, anchor_index: int, k: int, rng: random.Random):
    anchor = next(r for r in pool if r["measurement_index"] == anchor_index)
    before = [r for r in pool if r["elapsed_time_sec"] < anchor["elapsed_time_sec"]]
    selected = [anchor] + ([before[-1]] if before else [])
    selected_ids = {r["measurement_index"] for r in selected}
    remaining = [r for r in pool if r["measurement_index"] not in selected_ids]
    selected.extend(rng.sample(remaining, k - len(selected)))
    return sorted(selected, key=lambda r: (r["elapsed_time_sec"], r["measurement_index"]))


def build_manifest_rows(trajectories, splits, regimes, seed, anchor_cap):
    output = []
    for tkey, rows in sorted(trajectories.items()):
        if not rows or rows[0]["split"] not in splits:
            continue
        for context_min in CONTEXT_LENGTHS:
            min_k = math.floor(0.8 * context_min)
            eligible = [
                (pos, context_pool(rows, pos, context_min))
                for pos in range(len(rows))
                if len(context_pool(rows, pos, context_min)) >= min_k
            ]
            if anchor_cap is not None and len(eligible) > anchor_cap:
                rng = random.Random(stable_int(seed, tkey, context_min, "anchors"))
                eligible = sorted(rng.sample(eligible, anchor_cap))
            for anchor_pos, pool in eligible:
                anchor = rows[anchor_pos]
                anchor_index = anchor["measurement_index"]
                rng = random.Random(stable_int(seed, tkey, context_min, anchor_index, "context"))
                k = rng.randint(min_k, min(context_min, len(pool)))
                selected = select_context(pool, anchor_index, k, rng)
                future = [r for r in rows if r["elapsed_time_sec"] > anchor["elapsed_time_sec"]]
                for regime in regimes:
                    keep_prob = SPARSE[regime]
                    sparse_rng = random.Random(
                        stable_int(seed, tkey, context_min, anchor_index, regime, "sparse")
                    )
                    observed = [
                        r["measurement_index"] == anchor_index or sparse_rng.random() < keep_prob
                        for r in selected
                    ]
                    for ratio in RATIOS:
                        horizon_min = math.floor(context_min * ratio)
                        future_rows = [
                            r for r in future
                            if r["elapsed_time_sec"] <= anchor["elapsed_time_sec"] + horizon_min * 60
                        ]
                        if not future_rows:
                            continue
                        output.append({
                            "eval_schema_version": EVAL_SCHEMA,
                            "sample_id": sample_id(
                                EVAL_SCHEMA, tkey, anchor_index, context_min, ratio, regime, seed
                            ),
                            "dataset_name": tkey[0],
                            "experiment_id": tkey[1],
                            "bearing_id": tkey[2],
                            "split": anchor["split"],
                            "context_window_min": context_min,
                            "context_max_records": context_min,
                            "context_min_records": min_k,
                            "context_measurement_indices": [r["measurement_index"] for r in selected],
                            "context_relative_time_sec": [
                                r["elapsed_time_sec"] - anchor["elapsed_time_sec"] for r in selected
                            ],
                            "context_observed_mask": observed,
                            "context_count_k": k,
                            "context_observed_count": sum(observed),
                            "sparse_regime": regime,
                            "sparse_retention_probability": keep_prob,
                            "sampling_seed": stable_int(
                                seed, tkey, context_min, anchor_index, regime, ratio
                            ),
                            "anchor_measurement_index": anchor_index,
                            "anchor_elapsed_time_sec": anchor["elapsed_time_sec"],
                            "predict_ratio": ratio,
                            "predict_ratio_label": f"{ratio:g}x",
                            "predict_horizon_min": horizon_min,
                            "predict_horizon_sec": horizon_min * 60,
                            "future_measurement_indices": [r["measurement_index"] for r in future_rows],
                            "future_relative_time_sec": [
                                r["elapsed_time_sec"] - anchor["elapsed_time_sec"] for r in future_rows
                            ],
                            "future_query_count_q": len(future_rows),
                            "future_query_policy": "all_observed_within_horizon",
                            "context_policy": "uniform_k_keep_anchor_and_predecessor",
                            "target_policy": "observed_only_no_interpolation",
                        })
    return output


def write_json(path: Path, value: Any):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare(args):
    trajectories, _ = load_snapshot(args.snapshot_features)
    rows = build_manifest_rows(
        trajectories, set(args.split), args.sparse_regime, args.seed,
        args.max_anchors_per_trajectory,
    )
    if not rows:
        raise ValueError("no evaluation rows were generated")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), args.output)
    summary = {
        "eval_schema_version": EVAL_SCHEMA,
        "source_snapshot_features": str(args.snapshot_features),
        "output_manifest": str(args.output),
        "seed": args.seed,
        "splits": args.split,
        "sparse_regimes": args.sparse_regime,
        "context_windows_min": list(CONTEXT_LENGTHS),
        "min_records_by_context": {str(c): math.floor(0.8 * c) for c in CONTEXT_LENGTHS},
        "predict_ratios": list(RATIOS),
        "predict_horizons_min_by_context": {
            str(c): [math.floor(c * r) for r in RATIOS] for c in CONTEXT_LENGTHS
        },
        "rows": len(rows),
        "unique_samples": len({r["sample_id"] for r in rows}),
    }
    write_json(args.output.with_suffix(".json"), summary)
    print(json.dumps(summary, indent=2))


def parse_prediction_specs(specs):
    result = {}
    for spec in specs:
        name, sep, path = spec.partition("=")
        if not sep:
            path, name = spec, Path(spec).stem
        if not name or not path:
            raise ValueError(f"invalid --prediction value: {spec!r}")
        if name in result:
            raise ValueError(f"duplicate prediction model: {name}")
        result[name] = Path(path)
    return result


def prediction_arrays(row):
    point = row.get("predicted_features")
    if point is None:
        point = row.get("prediction_features")
    samples = row.get("prediction_samples")
    sample_array = None if samples is None else np.asarray(samples, dtype=float)
    if point is None and sample_array is None:
        raise ValueError("prediction row needs predicted_features or prediction_samples")
    if sample_array is not None:
        if sample_array.ndim != 3 or sample_array.shape[-1] != D:
            raise ValueError("prediction_samples must have shape [S, Q, 30]")
        point_array = np.mean(sample_array, axis=0) if point is None else np.asarray(point, dtype=float)
    else:
        point_array = np.asarray(point, dtype=float)
    if point_array.ndim != 2 or point_array.shape[-1] != D:
        raise ValueError("prediction features must have shape [Q, 30]")
    return point_array, sample_array


def load_predictions(specs):
    result = {}
    for model, path in specs.items():
        for row in pq.read_table(path).to_pylist():
            if not row.get("sample_id"):
                raise ValueError(f"prediction file {path} has a row without sample_id")
            key = (model, str(row["sample_id"]))
            if key in result:
                raise ValueError(f"duplicate prediction key: {key}")
            result[key] = prediction_arrays(row)
    return result


def target_arrays(record, snapshot_index):
    keys = [
        (record["dataset_name"], record["experiment_id"], record["bearing_id"], int(i))
        for i in record["future_measurement_indices"]
    ]
    rows = []
    for key in keys:
        if key not in snapshot_index:
            raise ValueError(f"manifest references missing target snapshot: {key}")
        rows.append(snapshot_index[key])
    values = np.asarray([r["feature_vector"] for r in rows], dtype=float)
    valid = np.asarray([r["feature_valid_mask"] for r in rows], dtype=bool)
    return values, valid & np.isfinite(values)


def dashboard(path: Path, metrics, report):
    data = json.dumps(metrics, ensure_ascii=False).replace("</", "<\\/")
    report_data = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    html = """<!doctype html><html><head><meta charset="utf-8">
<title>Context and horizon evaluation</title>
<style>body{font:14px system-ui;margin:24px}table{border-collapse:collapse}
th,td{border:1px solid #ccc;padding:6px 9px;text-align:right}
th{background:#eee}td:first-child,th:first-child{text-align:left}</style></head>
<body><h1>Context / horizon sensitivity</h1><p id="summary"></p>
<label>Model <select id="model"></select></label>
<label>Split <select id="split"></select></label>
<label>Sparse <select id="sparse"></select></label>
<label>Metric <select id="metric"><option value="rmse">RMSE</option>
<option value="mae">MAE</option></select></label>
<table><thead><tr><th>Context</th><th>Horizon</th><th>Ratio</th>
<th>Value</th><th>Coverage</th><th>Examples</th></tr></thead>
<tbody id="body"></tbody></table>
<script>
const rows=__ROWS__, report=__REPORT__;
const unique=k=>[...new Set(rows.map(r=>r[k]))].sort();
for(const [id,key] of [["model","model"],["split","split"],["sparse","sparse_regime"]]){
 const s=document.getElementById(id);
 for(const v of unique(key)){const o=document.createElement("option");o.value=v;o.textContent=v;s.appendChild(o)}
}
document.getElementById("summary").textContent="Metrics rows: "+rows.length+
 " | manifest samples: "+(report.generated_samples||0);
function render(){
 const model=document.getElementById("model").value, split=document.getElementById("split").value;
 const sparse=document.getElementById("sparse").value, metric=document.getElementById("metric").value;
 const selected=rows.filter(r=>r.group_name==="overall"&&r.model===model&&
 r.split===split&&r.sparse_regime===sparse).sort((a,b)=>
 a.context_window_min-b.context_window_min||a.predict_horizon_min-b.predict_horizon_min);
 document.getElementById("body").innerHTML=selected.map(r=>
 "<tr><td>"+r.context_window_min+"</td><td>"+r.predict_horizon_min+
 "</td><td>"+r.predict_ratio_label+"</td><td>"+Number(r[metric]).toFixed(4)+
 "</td><td>"+(100*r.cell_coverage).toFixed(1)+"%</td><td>"+
 r.evaluated_examples+"/"+r.cell_record_count+"</td></tr>").join("");
}
for(const id of ["model","split","sparse","metric"])
 document.getElementById(id).addEventListener("change",render);
render();
</script></body></html>"""
    path.write_text(html.replace("__ROWS__", data).replace("__REPORT__", report_data), encoding="utf-8")


def evaluate(args):
    _, snapshot_index = load_snapshot(args.snapshot_features)
    manifest_rows = pq.read_table(args.manifest).to_pylist()
    specs = parse_prediction_specs(args.prediction)
    predictions = load_predictions(specs)
    total = defaultdict(int)
    grouped = defaultdict(list)
    for record in manifest_rows:
        cell = (
            record["split"], record["sparse_regime"], int(record["context_window_min"]),
            float(record["predict_ratio"]), int(record["predict_horizon_min"]),
        )
        total[cell] += 1
        target, target_mask = target_arrays(record, snapshot_index)
        for model in specs:
            pred = predictions.get((model, record["sample_id"]))
            if pred is None:
                continue
            point, samples = pred
            if point.shape != target.shape:
                raise ValueError(f"shape mismatch for {model}/{record['sample_id']}")
            if not np.isfinite(point).all():
                raise ValueError(f"non-finite prediction for {model}/{record['sample_id']}")
            mask = target_mask & np.isfinite(point)
            if not mask.any():
                continue
            interval = None
            if samples is not None:
                if samples.shape[1:] != target.shape or not np.isfinite(samples).all():
                    raise ValueError(f"invalid prediction_samples for {model}/{record['sample_id']}")
                lower, upper = np.percentile(samples, [5, 95], axis=0)
                interval = (
                    float(np.mean((target[mask] >= lower[mask]) & (target[mask] <= upper[mask]))),
                    float(np.mean((upper - lower)[mask])),
                )
            error = np.abs(point - target)[mask]
            squared = ((point - target) ** 2)[mask]
            groups = (
                ("overall", "all"),
                ("bearing", record["bearing_id"]),
                ("condition", record["experiment_id"]),
                ("context_records", str(record["context_count_k"])),
            )
            for group_name, group_value in groups:
                key = (model, group_name, group_value, *cell)
                grouped[key].append((error, squared, interval))
    metrics = []
    for key, values in sorted(grouped.items(), key=str):
        model, group_name, group_value, split, sparse, context, ratio, horizon = key
        errors = np.concatenate([v[0] for v in values])
        squared = np.concatenate([v[1] for v in values])
        intervals = [v[2] for v in values if v[2] is not None]
        interval = None
        if intervals:
            interval = (
                float(np.mean([v[0] for v in intervals])),
                float(np.mean([v[1] for v in intervals])),
            )
        row = {
            "metrics_schema_version": METRICS_SCHEMA,
            "model": model,
            "group_name": group_name,
            "group_value": group_value,
            "split": split,
            "sparse_regime": sparse,
            "context_window_min": context,
            "predict_ratio": ratio,
            "predict_ratio_label": f"{ratio:g}x",
            "predict_horizon_min": horizon,
            "cell_record_count": total[(split, sparse, context, ratio, horizon)],
            "evaluated_examples": len(values),
            "cell_coverage": len(values) / total[(split, sparse, context, ratio, horizon)],
            "feature_sample_count": int(errors.size),
            "mae": float(np.mean(errors)),
            "rmse": float(math.sqrt(np.mean(squared))),
            "coverage_90": None if interval is None else interval[0],
            "mean_interval_width_90": None if interval is None else interval[1],
        }
        metrics.append(row)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(metrics), args.output_dir / "metrics.parquet")
    report = {
        "metrics_schema_version": METRICS_SCHEMA,
        "snapshot_features": str(args.snapshot_features),
        "manifest": str(args.manifest),
        "prediction_models": {name: str(path) for name, path in specs.items()},
        "manifest_rows": len(manifest_rows),
        "generated_samples": len({r["sample_id"] for r in manifest_rows}),
        "prediction_rows": len(predictions),
        "metrics_rows": len(metrics),
        "missing_predictions": {
            model: sum((model, r["sample_id"]) not in predictions for r in manifest_rows)
            for model in specs
        },
    }
    write_json(args.output_dir / "metrics.json", metrics)
    write_json(args.output_dir / "report.json", report)
    dashboard(args.output_dir / "dashboard.html", metrics, report)
    print(json.dumps(report, indent=2))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest="command", required=True)
    prepare_p = subs.add_parser("prepare")
    prepare_p.add_argument("--snapshot-features", type=Path, required=True)
    prepare_p.add_argument("--output", type=Path, required=True)
    prepare_p.add_argument("--split", nargs="+", default=["validation", "test"])
    prepare_p.add_argument("--sparse-regime", nargs="+", choices=tuple(SPARSE), default=list(SPARSE))
    prepare_p.add_argument("--seed", type=int, default=2026)
    prepare_p.add_argument("--max-anchors-per-trajectory", type=int)
    prepare_p.set_defaults(handler=prepare)
    eval_p = subs.add_parser("evaluate")
    eval_p.add_argument("--snapshot-features", type=Path, required=True)
    eval_p.add_argument("--manifest", type=Path, required=True)
    eval_p.add_argument("--prediction", action="append", nargs="+", required=True)
    eval_p.add_argument("--output-dir", type=Path, required=True)
    eval_p.set_defaults(handler=evaluate)
    return p


def main():
    args = parser().parse_args()
    if args.command == "evaluate":
        args.prediction = [item for group in args.prediction for item in group]
    args.handler(args)


if __name__ == "__main__":
    main()
