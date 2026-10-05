# Research Foundation: Sparse, Irregular Bearing Degradation Generation

**Status:** project source of truth  
**Scope:** predictive-fault/degradation generator, beginning with XJTU-SY  
**Last consolidated:** 2026-10-05

This document records the durable research decisions agreed with the project owner. It exists so that later work does not depend on chat history. Update it when a decision changes; do not quietly supersede it in code or experiments.

This document is not intended to prescribe every action that must be followed. Its purpose is to provide a clear understanding of what we are doing, why we are doing it, and what decisions have been made. If anything in this document appears unreasonable, outdated, or no longer appropriate for the project, we can and should discuss it and agree on a modification. Do not silently modify or override this document without discussion.

The goal is to do what is best for the project rather than blindly follow rigid rules or constraints. These decisions should serve as guidance and shared context, not as inflexible restrictions. Use sound engineering and research judgment when circumstances require it, and update this document when a meaningful decision changes.

## One-sentence problem

Infer a bearing's current degradation state from a sparse, irregular observation history, then generate a distribution of plausible future degradation trajectories at arbitrary future relative-time queries.

\[
\boxed{
\text{sparse irregular history}
\rightarrow
\text{current degradation state}
\rightarrow
\text{future degradation trajectories}
}
\]

For a history \(H_t\) and queries \(Q\), the target is:

\[
P(X_{future}\mid H_t,Q)
\]

where

\[
H_t=\{(X_i,\Delta t_i,C_i)\}_{i=1}^{K},
\qquad
Q=\{\Delta t_{f1},\ldots,\Delta t_{fn}\}.
\]

`X_i` is a sensor-derived feature vector, `Δt_i` is relative time to the current anchor (`0` at now), and `C_i` is the physical operating context. The output is multiple future trajectories, not one deterministic forecast nor one failure sample.

## Non-negotiable decisions

1. **Inference does not receive lifecycle fraction / percent lifetime.**  \(\tau=t/T_{failure}\) is offline metadata used only for analysis, sampling, evaluation, or optional auxiliary supervision. The deployed model learns the current state from history.
2. **Time input is relative, not absolute bearing age.** A monitoring system may begin observing a bearing late in life, so absolute training age has a semantic mismatch with inference. Use time relative to the query anchor for both history and future queries.
3. **Operating condition is physical context, not a condition ID as the main feature.** For XJTU-SY the raw contract stores `rotational_speed_rpm` and `radial_load_kn`; the feature/model layer may derive `rotation_speed_hz`, while later environments can add load, torque, temperature, pressure, and related physical variables.
4. **Start in feature space, not raw-waveform diffusion.** The MVP processes each vibration snapshot into roughly 32–128 interpretable statistical/spectral features. Raw waveform / STFT / CWT / learned encoders are later upgrades.
5. **Evaluation splits are by bearing (asset), never random rows.** A trajectory from a bearing must not be represented in both train and held-out test.
6. **Use XJTU-SY operating conditions as controlled domains before cross-dataset work.** Establish C1+C2 → C3 adaptation before trying IMS/NASA or factory data.
7. **Build baselines and evaluation before conditional diffusion.** Diffusion must demonstrate a benefit over persistence and irregular-time baselines.
8. **“Normal” is operational, not proof of physical pristine condition.** In XJTU, early-life/reference segments are proxies; do not claim the first measurement means a completely new bearing without dataset evidence.

## Research hypotheses

- **H1 — Temporal degradation learning:** irregular history can predict/generate future degradation within one domain.
- **H2 — Sparse robustness:** the method remains useful with extreme removal of observations (including up to 99% removal) and irregular sampling.
- **H3 — Controlled-domain adaptation:** a model trained on XJTU C1+C2 can adapt to C3 from plentiful target-normal observations plus very few target-degradation observations.

Only after H1–H3 are supported should other datasets be a priority.

## Initial XJTU-SY setting

- 15 run-to-failure bearings distributed across three operating conditions:
  - C1: 35 Hz / 12 kN
  - C2: 37.5 Hz / 11 kN
  - C3: 40 Hz / 10 kN
- Vibration has two channels, sampled at 25.6 kHz in 1.28-second snapshots (32,768 samples per snapshot), acquired periodically.
- Use condition vector `[f_rot, load]`, not merely labels `1`, `2`, and `3`.

## Architecture direction

```text
raw vibration
  → signal/feature pipeline
  → feature vector X + relative time Δt + operating context C
  → observation encoder
  → irregular history encoder (current state z_t)
  → conditional feature-space diffusion conditioned on z_t, C, and future Δt queries
  → future feature trajectories / distributional summaries
```

### Core modules and priorities

| Module | Responsibility | Priority |
|---|---|---|
| Dataset adapter | raw dataset → common observation schema | P0 |
| Signal pipeline | waveform → deterministic statistical/spectral features | P0 |
| Irregular history builder | random anchors, sparse/irregular history, future queries | P0 |
| Observation encoder | feature vector → embedding | P0 |
| Condition encoder | physical context → embedding | P1 |
| History encoder | time-aware Transformer main model; GRU-D / Neural CDE baselines | P1 |
| Degradation generator | conditional diffusion over future feature trajectory | P1 |
| Domain adapter | freeze generic model; fit lightweight target adapter | P2 |
| Evaluation | point, distribution, spectral, trajectory, downstream tests | P0 alongside models |

### Candidate representations

Initial features include RMS, standard deviation, kurtosis, skewness, peak, crest factor, peak-to-peak, band energy, spectral entropy, and related features. All transforms must be deterministic. Fit normalization on training bearings only, then transform validation/test.

## Data contracts

The canonical raw contract is deliberately based on the semantic intersection of XJTU-SY and NASA IMS, rather than on either dataset's file layout. A dataset adapter may derive fields from file names, experiment metadata, or channel mappings. One normalized record represents **one bearing × one measurement × one channel**, not necessarily one source file.

### Canonical raw observation (decided 2026-10-05)

```text
Observation {
  dataset_name: string,
  experiment_id: string,
  bearing_id: string,
  measurement_index: integer,
  elapsed_time_sec: float,

  rotational_speed_rpm: float,
  radial_load_kn: float,

  channel_id: string,
  channel_direction: enum(horizontal, vertical, unknown),
  sampling_rate_hz: float,
  signal_length: integer,
  vibration_signal: float32[]
}
```

`experiment_id` distinguishes an XJTU-SY operating condition or an IMS test. `measurement_index` is the normalized chronological order, regardless of whether the source uses numbered files or timestamps. Operating speed and load are experiment-level metadata attached by the adapter and normalized to RPM and kN. `signal_length` must equal `len(vibration_signal)` and is retained for validation. The adapter may split multi-channel source files into multiple observations.

`relative_time_sec` is intentionally not a raw observation field: it is computed per task as `elapsed_time_sec - anchor_elapsed_time_sec`. Source-only fields such as `source_timestamp`, `source_file`, `sensor_id`, and `signal_unit` are not part of the cross-dataset core contract; they may be retained in source-specific metadata. Failure time, lifecycle fraction, fault type, and health labels belong to offline metadata/evaluation, never the main inference observation.

### Trajectory task

```text
TrajectoryTask {
  asset_id: string,
  history: [
    {
      observation_id: string,
      features: float32[],
      relative_time_sec: float,
      condition: {
        rotational_speed_rpm: float,
        radial_load_kn: float
      }
    },
    ...
  ],
  future_queries_sec: float[],
  future_targets: float32[][],
  anchor_elapsed_time_sec: float
}
```

The initial code backbone is the three objects: `Trajectory`, `TrajectoryTask`, and `ModelPrediction`.

### Sampling rules

- Select a random anchor time rather than forecasting only from lifecycle start.
- Randomize history size, history locations, gaps, density, and horizon.
- Convert each history timestamp as `timestamp - anchor`; anchor is zero.
- Query arbitrary positive relative times, including irregular and eventually continuous values.
- Simulate density at 100%, 50%, 20%, 10%, 5%, and 1%.
- Compare regular, random-irregular, and clustered-irregular sampling.

## Experimental protocol

### In-domain evaluation

- Hold out entire bearings for validation and test.
- Evaluate dense, sparse, irregular, and variable-horizon histories.
- Baselines, in order: persistence (`X_future = X_current`), irregular linear trend, GRU-D, time-aware Transformer, optional Neural CDE.
- Evaluate point metrics (MAE, RMSE, correlation), distributional metrics (e.g., MMD and correlation structure), spectral metrics (PSD/FFT/band energy), trajectory metrics (DTW, trajectory correlation, HI monotonicity), and a downstream real-test task.
- Downstream comparison: train on real-only, synthetic-only, and real+synthetic; always test on real unseen bearings.

### Acceptance targets for research MVP

1. Raw XJTU → processed observations → task dataset is reproducible.
2. Sparse/irregular task sampling works across patterns.
3. The generator produces future trajectories, not just a point/failure class.
4. It beats persistence on most held-out real horizons.
5. It remains useful under sparse and irregular observation.
6. C1+C2 can adapt to C3 with few degradation examples.
7. Quality increases systematically from 0 → 1 → 3 → 5 → 10 target-degradation examples.

The often-mentioned +5% real+synthetic uplift is an engineering target, not a universal scientific threshold.

## Controlled-domain adaptation

The main factory-oriented benchmark is:

```text
source: C1 + C2
target: C3
adaptation: plentiful target-normal + 0/1/3/5/10/fuller target-degradation observations
test: target bearings held out from supervised support
```

Train a generic model, freeze it, and fit a lightweight adapter rather than fully fine-tuning on a few target samples.

Run source-target permutations: C1+C2 → C3, C1+C3 → C2, C2+C3 → C1.

Two valid adaptation protocols must be distinguished:

- **Inductive:** only support-bearing target normal/fault observations are seen during adaptation; test bearings are wholly unseen.
- **Transductive (main factory-oriented protocol):** normal observations from the test machine may be used, while degradation labels remain few-shot support only.

## Factory-like simulation

Before actual factory deployment, downsample and randomize the periodic XJTU trajectory into a sparse calendar-like observation schedule. The full trajectory is ground truth; observed points form history and hidden future points form test. Benchmark at 1%, 5%, 10%, and 20% observation density. This establishes whether the system works in the intended sparse-monitoring scenario.

## Roadmap and dependency order

```text
1. Problem formulation + data contract + experiment protocol
2. Reproducible environment and dataset versioning
3. XJTU ingestion/parser and metadata
4. Signal/feature extraction and train-only normalization
5. Full trajectory object + random sparse/irregular task sampler
6. Persistence and linear baselines
7. Time-aware Transformer baseline (optional GRU-D/CDE)
8. Evaluation framework and unseen-bearing tests
9. Conditional feature-space diffusion and multi-trajectory sampling
10. In-domain sparse/irregular evaluation
11. C1+C2 → C3 target adapter and few-shot curve
12. Ablations and factory-like simulation
13. Serving/model registry only after model stability
```

Do not start Transformer or diffusion before the loader, feature pipeline, trajectory/sampler, and simple baselines exist.

## Future serving contract (not MVP work)

`POST /v1/generate` should accept observations, relative times, conditions, future queries, and `num_samples`; return generated trajectories, P10/P50/P90 or mean/median summaries, uncertainty, and version metadata. The inference pipeline loads the model once at startup: raw observations → features → relative-time builder → history encoder → diffusion sampler → decoder/post-processing.

Every registered model must be associated with `model_version`, `dataset_version`, `feature_schema_version`, `config_version`, `git_commit`, and `training_seed`.

## Technology preferences

- Python 3.11; PyTorch; NumPy; SciPy; pandas; PyArrow; scikit-learn.
- Hydra/OmegaConf/Pydantic for configuration and contracts.
- Parquet plus Zarr/HDF5 as needed; DVC for dataset/pipeline versioning; MLflow for runs and model lineage/registry.
- pytest, ruff, and mypy; Matplotlib/Plotly for analysis.
- FastAPI/Uvicorn/Docker only after research validation.
- An 8 GB GPU (e.g., GTX 1070) is appropriate for a small feature-space prototype using mixed precision and gradient accumulation; it is not the justification for raw-waveform diffusion.

## Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-10-04 | Use sparse irregular history → current state → future trajectory formulation. | Matches deployment observation reality. |
| 2026-10-04 | Exclude lifecycle fraction from main inference input. | Prevents lifetime-information leakage and makes inference feasible without failure time. |
| 2026-10-04 | Use relative time as the primary temporal signal. | Avoids training/inference semantic mismatch in observed age. |
| 2026-10-04 | Treat XJTU conditions as controlled domains before external datasets. | Enables credible, controlled adaptation evidence. |
| 2026-10-04 | Begin with feature-space generation. | Keeps the MVP debug-friendly and feasible on available compute. |
| 2026-10-05 | Adopt the canonical raw `Observation` contract defined above. | Provides one lossless, dataset-agnostic ingestion unit for XJTU-SY and IMS while keeping task-relative time and offline labels separate. |

