# Project Decisions

## IMPORTANT — Canonical cross-dataset Observation contract

**Decision:** Adopt the following canonical raw observation contract for the initial XJTU-SY and NASA IMS ingestion pipeline:

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

**Date:** 2026-10-05

**Problem addressed:** XJTU-SY and IMS do not share the same source-file layout. XJTU-SY stores a bearing snapshot with horizontal/vertical columns, while IMS contains multiple experiments and can contain multiple bearing/channel columns in one source file. A contract tied to a file layout would either lose channel/bearing identity or force dataset-specific model code.

**Current system state:** The project has no ingestion implementation yet. The research foundation previously described a generic `Observation` as `{asset_id, timestamp, features, condition}`; this decision replaces that placeholder with the raw, lossless, normalized observation contract. `TrajectoryTask` remains a derived training object.

**Business/project requirements:**
- one reproducible loader path for both initial datasets;
- preserve raw vibration so features can be recomputed;
- support bearing-level train/validation/test splits;
- represent sparse and irregular history without leaking lifecycle fraction;
- retain operating context for controlled-domain adaptation;
- keep source-specific quirks out of model code.

**Alternatives considered:**
1. Keep separate XJTU-SY and IMS schemas. Rejected because downstream trajectory/task/model code would be duplicated and cross-dataset adaptation would be harder to audit.
2. Treat one source file as one observation. Rejected because IMS files can contain multiple bearings/channels.
3. Use a feature-only contract. Rejected because raw waveform provenance and reproducible feature extraction would be lost.
4. Put `relative_time_sec` in raw observations. Rejected because relative time depends on the task's chosen anchor.
5. Make source-only fields such as `source_timestamp`, `sensor_id`, and `signal_unit` mandatory. Rejected because they are not uniformly available or documented across both datasets.

**Rationale:** The selected schema is the smallest lossless semantic intersection that both adapters can produce. `experiment_id` disambiguates conditions/tests; `bearing_id` supports asset-level splits; `measurement_index` and `elapsed_time_sec` preserve chronology; speed/load preserve physical operating context; `channel_id` and `channel_direction` preserve the sensor dimension; sampling rate, length, and waveform make signal processing reproducible. Fields may be derived from experiment metadata or source file names—the contract describes the normalized dataset, not the original columns.

**Evidence and assumptions:**
- XJTU-SY documentation describes 15 run-to-failure bearings, three speed/load conditions, two accelerometers (horizontal and vertical), 25.6 kHz sampling, 32,768 points per snapshot, and one CSV per sampling event: <https://www.researchgate.net/profile/Biao-Wang-27/publication/338596319_XJTU-SY_Bearing_Datasets/data/5eb689ee299bf1287f77f443/Introduction-to-XJTU-SY-Bearing-Dataset-NEW.pdf>
- NASA's official repository identifies IMS as the Bearings dataset provided by IMS/University of Cincinnati and links its archive: <https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/>
- Operating speed and load are treated as experiment-level metadata and normalized to RPM and kN.
- `signal_length` is a validation field and must equal the waveform length.
- The adapter will produce one normalized row per bearing × measurement × channel, even if one source file contains several channels.

**Consequences:**
- Positive: one common ingestion and trajectory interface; raw waveform is retained; channel-aware and bearing-aware splits are possible; task-relative time stays separate from source chronology.
- Negative: adapters must resolve source-to-bearing/channel mappings; experiment metadata may be repeated or joined; some source-specific information lives outside the core contract; raw waveforms can be large.
- The contract is intentionally raw-layer oriented; feature vectors belong to the derived observation/task layer.

**Reconsideration conditions:**
- Add a target dataset that cannot provide bearing identity, chronological order, or a vibration waveform without an explicit adapter strategy.
- Archive inspection disproves the assumed channel mapping or operating metadata.
- A future modeling requirement needs a different atomic unit (for example, multi-channel observations as one tensor) and the conversion remains lossless.
- The project formally expands beyond vibration bearing datasets; then version the contract rather than silently changing it.

## IMPORTANT — Define experiment protocol for causal XJTU forecasting

**Decision:** Use a causal, bearing-grouped protocol for initial XJTU-SY forecasting and fault generation. XJTU-SY is the current development dataset; IMS is deferred to a separate cross-dataset evaluation. The model receives recent sensor history and predicts a variable-length future sequence until failure, without condition metadata or absolute lifecycle age.

**Date:** 2026-10-07

**Problem addressed:** Random snapshot/window splits, absolute lifecycle time, total trajectory length, failure time, and laboratory condition identifiers can let the model exploit bearing identity or experimental structure instead of learning future signal behavior. Real operation may have changing conditions, irregular observations, and large bearing-to-bearing lifetime variation.

**Current system state:** The raw Observation contract is fixed. XJTU-SY evaluates generalization between physical bearing instances and between conditions. All XJTU bearings share one nominal model, so this is not transfer between bearing models.

**Business/project requirements:** Use recent sensor history; support irregular observations without interpolating missing waveforms; support configurable horizons and full rollout until failure; predict future sensor signals, relative future offsets, time-local fault state, and per-record confidence; separate bearing-instance from condition generalization; preserve a later XJTU-to-IMS evaluation.

**Protocol:**

1. At anchor t, use at most 20 valid records within the previous 30 minutes (max_records = 20; max_lookback = 1800 seconds). Each record contains sensor signal, relative lag_from_now, and masks for padding or unavailable channels/records. Same-timestamp horizontal and vertical signals are channels of one measurement. The main protocol requires at least 10 records; contexts of 1–9 are a separate robustness evaluation. Do not interpolate missing records or waveforms.
2. Exclude condition metadata, dataset_name, experiment_id, bearing_id, file/path identifiers, absolute start time, total operating age, measurement_index, total trajectory length, remaining life, and true failure time. Speed/load remain in raw data for provenance but are excluded from baseline input. Learned preprocessing is fit on train only.
3. Predict a variable-length sequence of future records. Each contains future sensor signal, relative future offset, time-local fault_state, and confidence. End with failure_event = 1 or END_OF_TRAJECTORY. A finite requested horizon is a truncated rollout. Keep terminal_fault_type as a trajectory-level target separate from fault_state because XJTU lacks reliable timestamp-level fault labels.
4. For each anchor, future observations are chronological from after t through the observed failure; future observations are never inputs. Final fault metadata may supervise targets but may not be input. Confidence is part of the interface; its loss and calibration are deferred to model design.
5. Use two XJTU tracks: unseen bearing within the same condition, with grouped leave-one-bearing-out and inner grouped validation; and unseen condition, with leave-one-condition-out, all five bearings of one condition in test, validation only from source conditions, and rotation across all three conditions. Split complete bearing trajectories before windows/features/synthetic records; never random-split overlapping windows. Synthetic data cannot use validation/test trajectories for training.
6. Report by bearing, condition, fault state/type, history length, and horizon. Include persistence and simple autoregressive baselines, leakage canaries, and duplicate/near-duplicate checks. XJTU-to-IMS is a separate zero-shot experiment unless adaptation is declared.

**Alternatives considered:** Random snapshot/window splits, condition metadata, absolute lifecycle variables, unlimited history, missing-waveform interpolation, fixed-length output, and treating terminal fault type as a timestamp-level label were rejected for leakage, deployment mismatch, fabricated content, or ambiguous supervision.

**Rationale:** Bearing-grouped splits prevent identity and temporal-neighbor leakage. Bounded recent history with relative lags matches causal deployment. The two XJTU tracks isolate instance variation from condition variation before external domain shift. A termination event makes full-to-failure prediction well-defined while retaining finite-horizon queries. Separating fault_state from terminal_fault_type distinguishes time-local state from eventual failure mechanism.

**Evidence and assumptions:** XJTU-SY documents 15 run-to-failure bearings under three conditions, five per condition, using a common nominal model: <https://github.com/WangBiaoXJTU/xjtu-sy-bearing-datasets> and <https://www.researchgate.net/profile/Biao-Wang-27/publication/338596319_XJTU-SY_Bearing_Datasets/data/5eb689ee299bf1287f77f443/Introduction-to-XJTU-SY-Bearing-Dataset-NEW.pdf>. Observations are approximately one minute apart; fault metadata are trajectory-level final information unless a documented timestamp-level labeling procedure is introduced.

**Consequences:** Leakage boundaries and evaluation scopes are explicit; irregular history, configurable horizons, within-condition generalization, and unseen-condition evaluation are supported. Grouped manifests, inner validation, masks, termination handling, and per-bearing aggregation are required. Architecture and confidence loss remain downstream decisions.

**Reconsideration conditions:** Reliable deployment condition metadata becomes available; validation shows the 30-minute/20-record context is unrepresentative; a validated timestamp-level labeling procedure changes fault_state; or a new dataset/bearing model requires a separately versioned transfer protocol.
