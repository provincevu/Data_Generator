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

## IMPORTANT — Define XJTU-SY parse-time chronology and waveform-length policy

**Decision:** For XJTU-SY, interpret the numeric CSV filename as the source measurement number: `n.csv` is measurement `n`, approximately one minute after the preceding measurement. Preserve this value as `measurement_index`. Define normalized elapsed time from source measurement 1 as `elapsed_time_sec = (measurement_index - 1) * 60`. Keep the actual waveform length in `signal_length`; do not reject a file solely because its length differs from 32,768 samples. The raw parser must preserve the samples as read. Local repair of a small number of missing samples, if needed, is a separate preprocessing step and must not overwrite the raw representation.

**Date:** 2026-10-08

**Problem addressed:** XJTU-SY CSV files do not contain an explicit timestamp, and waveform length may vary with the effective sampling rate or minor acquisition loss. Treating filename order as a newly generated sequential index, forcing every waveform to 32,768 samples, or repairing data during raw parsing would blur provenance and mix ingestion with preprocessing.

**Current system state:** The canonical `Observation` contract and causal experiment protocol are fixed. The XJTU-SY raw tree contains one CSV per measurement, with horizontal and vertical signal columns. The initial sample inspection found 32,768 data rows in representative files, but this is not treated as an unconditional parser requirement.

**Business/project requirements:** Preserve source chronology and bearing provenance; support irregular or missing measurements; retain the raw signal for reproducible downstream processing; avoid discarding usable records because of small length deviations; keep any imputation auditable and reversible.

**Alternatives considered:**
1. Use `measurement_index * 60` as elapsed time. Rejected for the normalized trajectory representation because source measurement 1 should be the time origin; the source minute number remains available in `measurement_index`.
2. Renumber files after detecting gaps. Rejected because it would hide missing measurements and damage source chronology.
3. Require exactly 32,768 samples. Rejected because signal length depends on acquisition details and small deviations do not necessarily make a measurement unusable.
4. Interpolate or pad samples during raw parsing. Rejected because the raw layer must remain lossless and preprocessing policy should be independently testable.
5. Interpolate missing measurements. Rejected because a missing one-minute observation is a real temporal gap, not a missing waveform sample.

**Rationale:** The filename is the only available source chronology for XJTU-SY, so its numeric value must be preserved. Using source measurement 1 as time zero makes elapsed time a trajectory-relative quantity while retaining the original minute number. A 1.28-second acquisition at 25.6 kHz gives 32,768 samples as an expected value, not a universal contract. Keeping the observed length and raw samples avoids fabricating data; a later cleaning step can make a narrowly scoped, auditable decision about local sample repair.

**Evidence and assumptions:** The XJTU-SY tree uses numeric CSV filenames such as `1.csv`, `2.csv`, and `100.csv`; each inspected file has horizontal and vertical columns. The dataset acquisition is approximately one measurement per minute and approximately 1.28 seconds per measurement at 25.6 kHz. A missing CSV is treated as a missing observation, while a short or locally incomplete waveform is treated as a signal-quality issue to be reported separately.

**Consequences:** The parser can preserve chronology without requiring timestamps, tolerate legitimate length variation, and keep raw data unchanged. The manifest and validation report must record missing measurement numbers, actual signal lengths, and any parse anomalies. A future cleaning step needs explicit thresholds, masks, and provenance if local repair is introduced.

**Reconsideration conditions:** The source dataset provides authoritative timestamps; the one-minute cadence is shown to be materially different or irregular; acquisition metadata proves that short waveforms represent truncation rather than harmless variation; or downstream analysis requires a different time origin. Any decision to repair raw samples in place would require revising this record.
## IMPORTANT — Normalize XJTU-SY metadata as separate source-backed layers

**Decision:** Store XJTU-SY metadata outside the canonical raw Observation table in three layers: one dataset metadata row, three condition metadata rows, and one trajectory metadata row per bearing. Use `configs/xjtu_trajectory_metadata.csv` as the editable source mapping for Table 2 trajectory metadata. Generate Parquet outputs from that mapping and the parsed source manifest. Preserve `fault_element_raw` and `reported_lifetime_raw`; store normalized `fault_elements` separately as a list. Derive parsed measurement counts and index bounds from the manifest. Do not create timestamp-level `fault_state` labels from the PDF.

**Date:** 2026-10-08

**Problem addressed:** The PDF provides dataset, condition, bearing lifetime, file-count, and fault-element information, but these fields have different scopes and must not be mixed into the raw Observation contract or treated as timestamp-level supervision.

**Current system state:** XJTU-SY raw CSV files have been parsed into `xjtu_observations.parquet` and `xjtu_source_manifest.parquet`. The PDF Table 2 contains metadata for all 15 bearings. The normalization implementation creates `xjtu_dataset_metadata.parquet`, `xjtu_condition_metadata.parquet`, `xjtu_trajectory_metadata.parquet`, and `xjtu_metadata_report.json` under `data/interim/xjtu/`.

**Business/project requirements:** Keep source labels and provenance auditable; support condition and trajectory-level EDA; preserve the distinction between reported lifetime and normalized Observation elapsed time; allow normalized multi-label fault elements; prevent metadata leakage into the baseline model input; make manual metadata corrections reviewable without changing parser code.

**Alternatives considered:**
1. Put all metadata into each raw Observation. Rejected because metadata scopes differ and the canonical raw contract should remain stable and lossless.
2. Parse the PDF at runtime. Rejected because PDF extraction is fragile and manual corrections should be explicit and reviewable.
3. Store only normalized fault labels. Rejected because the source wording and provenance must remain recoverable.
4. Use `reported_lifetime_min` as Observation `elapsed_time_sec`. Rejected because reported lifetime and the project's trajectory-relative time convention are distinct.
5. Infer timestamp-level fault state from the final fault element. Rejected because the PDF provides trajectory-level fault information, not reliable timestamp labels.

**Rationale:** A small, editable CSV is an appropriate source of truth for the 15-row Table 2 mapping, while Parquet is appropriate for downstream data work. Separate dataset, condition, and trajectory tables make scope explicit. Joining the trajectory table to the parsed manifest provides derived counts and measurement bounds without modifying raw observations. Keeping raw and normalized labels side by side preserves both auditability and usability.

**Evidence and assumptions:** The source PDF documents 15 bearings, three conditions, sampling metadata, reported lifetimes, CSV counts, and fault elements in Table 2. The current parsed manifest contains all 9,216 source files with matching bearing/condition keys and no count mismatches. `fault_elements` uses the controlled vocabulary `inner_race`, `outer_race`, `cage`, and `ball`.

**Consequences:** Metadata corrections can be made in the configuration CSV and regenerated. Downstream code must join metadata by `dataset_name`, `experiment_id`, and `bearing_id`. The mapping file and generated Parquet outputs must be kept synchronized. Metadata remains available for EDA and target construction but is excluded from baseline model inputs according to the experiment protocol.

**Reconsideration conditions:** A revised authoritative dataset document changes Table 2; a validated timestamp-level labeling procedure becomes available; metadata must support another dataset with incompatible scopes; or the project requires a versioned metadata ontology beyond the current four fault-element labels.
## IMPORTANT — Use eleven normalized trajectory anchors for XJTU-SY FFT EDA

**Decision:** The XJTU-SY EDA will compute frequency-domain summaries using eleven normalized trajectory anchors: 0%, 10%, 20%, ..., 100%. The 0% anchor is the first available source measurement and the 100% anchor is the last available source measurement for each bearing. Intermediate anchors select the nearest measurement by trajectory position, using the measurement index among that bearing's ordered observations; the selected source measurement index remains recorded in the EDA output.

**Date:** 2026-10-08

**Problem addressed:** XJTU-SY trajectories have very different numbers of measurements. Selecting the same absolute measurement numbers would make FFT comparisons represent different lifecycle stages across bearings.

**Current system state:** Raw observations and trajectory metadata are normalized. The EDA scope includes time-domain summaries for all measurements and frequency-domain summaries at selected representative points. No FFT output has been generated yet.

**Business/project requirements:** Compare spectral evolution across bearings, conditions, channels, and trajectory-level fault elements while preserving the original measurement index and avoiding interpolation or invented observations.

**Alternatives considered:**
1. Use only first, middle, and last measurements. Rejected because it is too coarse for observing gradual spectral evolution.
2. Use fixed absolute measurement indices. Rejected because bearing trajectories have different lifetimes and file counts.
3. Resample or interpolate every trajectory to a common length. Rejected because it would create synthetic waveform observations and blur source chronology.
4. Compute FFT for every measurement. Deferred because it increases computation and storage without being necessary for the first comparative EDA pass.

**Rationale:** Eleven equally spaced normalized positions provide a consistent lifecycle grid across trajectories while keeping the original waveform unchanged. Nearest-measurement selection is deterministic, auditable, and does not fabricate data. Recording both the normalized anchor and selected `measurement_index` preserves interpretability.

**Evidence and assumptions:** Table 2 of the XJTU-SY dataset document reports substantially different trajectory lengths, from 42 to 2,538 CSV files. Each CSV contains the horizontal and vertical waveform for one sampling event.

**Consequences:** The EDA output must include `anchor_fraction`, `selected_measurement_index`, `channel_id`, and the FFT summary fields. Some adjacent anchors may select the same measurement for very short trajectories; this is acceptable and must be reported rather than hidden.

**Reconsideration conditions:** A downstream task requires a different lifecycle alignment, a validated timestamp-level event alignment becomes available, or the EDA needs full per-measurement spectral analysis.
## IMPORTANT — Define the initial XJTU-SY FFT preprocessing contract

**Decision:** For the initial XJTU-SY FFT EDA, subtract the waveform mean and apply a Hann window before computing a one-sided real FFT. Store the frequency grid and one-sided amplitude spectrum together with the dominant frequency, dominant amplitude, total spectral power, and four fixed band-power summaries. Keep the observed waveform length and sampling rate in every FFT row.

**Date:** 2026-10-08

**Problem addressed:** A reproducible FFT summary needs an explicit treatment of the waveform mean, spectral leakage, amplitude scaling, and variable waveform length. Leaving these choices implicit would make later comparisons difficult to reproduce.

**Current system state:** The EDA implementation writes one time-domain summary row per Observation and 330 FFT rows for 15 trajectories × 2 channels × 11 anchors. The raw waveform is not modified.

**Business/project requirements:** Make the first EDA pass deterministic and auditable; preserve enough spectral information for later plots and analysis; tolerate waveform lengths that differ from 32,768 samples.

**Alternatives considered:** Raw FFT without centering or windowing; zero-padding or resampling to a fixed length; storing only a dominant frequency; and computing a full spectrum for every measurement. These were deferred or rejected because they either leave leakage and scaling ambiguous, fabricate samples, discard useful information, or add unnecessary initial cost.

**Rationale:** Mean subtraction removes the DC component that is not the focus of the vibration comparison. The Hann window reduces leakage for finite acquisition windows. A one-sided real FFT preserves the positive-frequency content, while retaining the full frequency and amplitude arrays keeps the output reusable. The observed length remains authoritative, so frequency resolution is recorded per row rather than assumed constant.

**Consequences:** FFT outputs are directly comparable when sampling rates match, but spectra from different lengths have different frequency resolutions and should be compared using their recorded frequency grids or an explicitly documented interpolation for plotting. The output is larger than a scalar-only summary. The initial implementation uses fixed bands 0–1 kHz, 1–5 kHz, 5–10 kHz, and 10–12.8 kHz for the documented 25.6 kHz sampling rate.

**Reconsideration conditions:** A downstream method requires a different amplitude calibration, window, detrending policy, spectral density estimate, frequency grid, or sampling-rate normalization; or the project adopts full per-measurement spectral storage.

## IMPORTANT — Define XJTU-SY time-domain statistics

**Decision:** Store std = sqrt(E[(x - mean)^2]), raw Pearson kurtosis E[(x - mean)^4] / std^4, and crest_factor = peak_abs / RMS for every Observation and channel in the EDA signal summary. Use population moments over the samples within one waveform; return undefined kurtosis or crest factor as NaN when the variance or RMS is zero.

**Date:** 2026-10-08

**Problem addressed:** The EDA needs explicit, reproducible definitions for three waveform statistics that will later be displayed in lifecycle animations and used for comparisons.

**Rationale:** The requested kurtosis is the raw standardized fourth central moment, not SciPy's excess kurtosis. Population moments match the expectation notation and avoid silently subtracting 3 or using a sample correction. Crest factor captures impulsiveness relative to the waveform's RMS.

**Consequences:** Existing xjtu_signal_summary.parquet must be regenerated after implementation changes. Downstream users must not interpret kurtosis as excess kurtosis.

**Reconsideration conditions:** A later analysis explicitly requires unbiased sample estimators or excess kurtosis; then introduce a separately named field rather than changing this field silently.

## IMPORTANT — Cache reusable XJTU-SY EDA stages and use Vietnamese plot labels

**Decision:** The XJTU-SY EDA pipeline stores a cache manifest at xjtu_eda_cache.json. It independently caches the time-summary Parquet, the FFT-summary Parquet, and the seven static plots. Each cache entry is reused only when its input file signatures and stage version/configuration match; changing one stage invalidates only that stage and downstream plots. Add a force-recompute option for intentional invalidation. Static plot titles, axes, legends, and explanatory notes are Vietnamese while identifiers and standard metric names remain recognizable.

**Date:** 2026-10-09

**Problem addressed:** Re-running EDA after a plotting or label change unnecessarily reread the 1.91 GB waveform Parquet, and English-only labels made the figures harder to interpret.

**Current system state:** The EDA has time summaries for all observations, FFT summaries at 11 anchors, and static lifecycle/FFT/lifetime plots. The cache manifest records stage keys based on input size/modified time and stage configuration versions.

**Business/project requirements:** Make iterative EDA development practical on the local dataset, avoid silently using stale results, explain figures in Vietnamese, and preserve an explicit escape hatch for a full rebuild.

**Alternatives considered:** Recompute every stage on every run; cache only the final report; use one global cache key; or reuse outputs solely because files exist. These alternatives waste resources or risk stale or partial outputs.

**Rationale:** Stage-level keys allow a plot-only change to reuse both Parquet summaries, while a raw-data or metric-definition change invalidates the time summary and its downstream stages. File signatures are cheaper than hashing the 1.91 GB input on every invocation; stage versions/configuration provide explicit invalidation for code changes. Vietnamese labels and short notes make the figures usable without translating every axis manually.

**Consequences:** The first run still processes the full raw-derived Parquet. A changed implementation must update its stage version/configuration or use force-recompute. A deleted or mismatched cache causes the affected stage to rebuild. Plot files are still ignored by Git.

**Reconsideration conditions:** Inputs are stored on a filesystem where size and modified time are unreliable; concurrent EDA writers need coordination; or the cache must be portable across machines, in which case content hashes and environment fingerprints may be required.

## IMPORTANT — Fix the XJTU-SY Phase 3 feature schema and leakage-safe preprocessing

**Decision:** Define feature schema version `xjtu_feature_v1` as 15 scalar features per channel, ordered as `mean`, `std`, `rms`, `peak_abs`, `peak_to_peak`, `kurtosis`, `crest_factor`, `dominant_frequency_hz`, `dominant_amplitude`, `total_spectral_power`, `spectral_entropy`, `band_power_0_1000_hz`, `band_power_1000_5000_hz`, `band_power_5000_10000_hz`, and `band_power_10000_12800_hz`. Define each physical snapshot vector as horizontal features followed by vertical features, so `D = 30`. Keep the raw contract one row per channel; the derived snapshot feature table has one row per bearing × measurement and carries channel-presence and feature-validity masks.

Compute the scalar spectral features for every observation using the existing mean-centering and Hann-window policy. Spectral entropy is normalized Shannon entropy of the windowed one-sided power spectrum. Do not add STFT to Phase 3.

Use a deterministic baseline grouped split for preprocessing: condition 3 is test; `Bearing1_5` and `Bearing2_5` are validation; all other bearings are train. Fit per-feature z-score statistics using finite values from train bearings only. Missing or undefined values are replaced by the train mean before scaling and are marked by masks; do not clip or delete outliers automatically.

**Date:** 2026-10-09

**Problem addressed:** The project had interpretable time-domain and anchor-only FFT EDA, but no fixed-dimensional feature vector for every snapshot, no spectral entropy, and no leakage-safe normalization or automated feature-quality report before modeling.

**Current system state:** Raw XJTU-SY observations, metadata, time summaries, and 11-anchor FFT summaries exist. The new derived feature pipeline creates per-channel features for every observation, a 30-dimensional per-snapshot table, a train-only scaler, and a validation report covering non-finite values, constants, robust outliers, and high correlations.

**Business/project requirements:** Finish the debug-friendly feature-space MVP before diffusion; preserve raw waveform provenance; make every snapshot comparable in a fixed feature space; prevent validation/test distribution from affecting preprocessing; retain enough masks and reports to audit missing or undefined values.

**Alternatives considered:**
1. Keep variable-length FFT arrays as model inputs. Rejected because they do not define a fixed `D` when waveform length varies.
2. Compute spectral features only at the 11 EDA anchors. Rejected for model features because the model needs a representation for every snapshot.
3. Add STFT immediately. Deferred because the initial fixed-window FFT and band features are sufficient for the MVP and the project explicitly treats STFT as a later upgrade.
4. Fit normalization on all trajectories. Rejected because it leaks validation/test distribution information.
5. Automatically remove outliers or correlated features. Rejected because the first validation stage should report evidence without silently changing raw-derived information.
6. Use a single channel-combined raw Observation. Rejected because the canonical raw contract preserves one row per channel; channel packing belongs only to the derived snapshot layer.

**Rationale:** Fifteen scalar features per channel cover the already-approved time statistics and the first spectral summary while remaining deterministic and auditable. Concatenating the two documented channels produces a stable 30-dimensional snapshot vector without changing raw provenance. The baseline split follows the project requirement for bearing/condition grouping and leaves a clear path to later rotating leave-one-condition-out folds. Train-only z-score scaling is simple, reproducible, and does not destroy amplitude information through clipping. Masks make imputation explicit rather than hiding missing or mathematically undefined values.

**Evidence and assumptions:** The XJTU-SY source documents horizontal and vertical channels, 25.6 kHz sampling, and approximately 32,768 samples per measurement. Existing project decisions already fix mean-centering, Hann preprocessing, four frequency bands, raw Pearson kurtosis, and crest-factor definitions. Current data has both channels for every parsed measurement; mask behavior is included for future incomplete inputs.

**Consequences:** Phase 3 produces `xjtu_observation_features.parquet`, `xjtu_snapshot_features.parquet`, `xjtu_feature_scaler.json`, `xjtu_feature_validation.json`, and `xjtu_feature_report.json`. The snapshot table has fixed `D = 30`; normalized vectors can be passed to a baseline model or diffusion prototype. STFT, learned encoders, automatic feature selection, and outlier repair remain future work. The baseline validation/test assignment is a preprocessing convention, not the final model-evaluation fold generator.

**Reconsideration conditions:** A downstream model requires a different channel packing, a validated timestamp-level fault representation, a different sampling-rate regime, rotating evaluation folds, a different normalization family, or evidence that the chosen 15-feature-per-channel schema omits important degradation information. Any such change must version the feature schema and update both decision records.

## IMPORTANT — Make lifecycle generation suitable for health prediction

**Decision:** Treat five requirements as mandatory acceptance criteria for every generated lifecycle used by RUL, health-index, degradation-stage, or failure-prediction models: explicit healthy/FPT/degradation/EOL progression; physically meaningful time- and frequency-domain evolution with periodic impacts; labels synchronized from the generation state; stochastic lifecycle variability with reproducible seeds; and synchronized multi-sensor channels with direction-dependent signal differences.

**Date:** 2026-10-09

**Problem addressed:** A lifecycle generator that only scales healthy amplitude can produce visually plausible files while teaching an AI model shortcuts such as RMS magnitude. It does not provide a learnable transition, physical fault-frequency evidence, aligned targets, realistic variation, or consistent multi-channel behavior.

**Current system state:** The project has XJTU-SY raw observations, metadata, EDA, and feature extraction. The durable requirements for a future synthetic lifecycle generator had not yet been recorded as mandatory project instructions. The canonical raw XJTU layer remains source-backed and must not be confused with synthetic labels.

**Business/project requirements:** Generate data that can support supervised RUL or degradation-stage learning; preserve a healthy baseline; expose FPT and EOL; provide RUL and HI for every sample; create different but reproducible failure scenarios; and represent horizontal/vertical sensors as channels of the same physical lifecycle.

**Alternatives considered:** Accept amplitude-only scaling; impose a single deterministic monotonic degradation curve; generate labels after waveform generation from filenames; create independent sensor channels; or leave physical fault frequencies as an optional visual effect without a periodic impact mechanism. These alternatives were rejected because they encourage shortcut learning, hide state transitions, break label synchronization, violate multi-sensor physics, or make fault-frequency learning impossible.

**Rationale:** The five requirements together constrain the most important failure modes of synthetic predictive-maintenance data. A shared latent health state makes waveform and labels consistent; FPT-based piecewise RUL gives a clear supervised target; periodic impacts and characteristic frequencies provide structure beyond amplitude; stochastic lifetime and noise variation reduce memorization; and shared timing across channels preserves the physical meaning of a multi-sensor observation. Seeds and generation parameters make failures reproducible and auditable.

**Consequences:** Future lifecycle generators must document FPT, EOL, stage, RUL, HI, seed, and generation parameters per sample or lifecycle. They must expose enough time/frequency features to review the transition and must not claim physical accuracy when geometry or calibration is unknown. Any intentional exception requires a new reviewed decision in both language versions. These requirements may increase generator complexity and make naive visual validation insufficient.

**Reconsideration conditions:** A validated real-data study demonstrates that a requirement is irrelevant to the target deployment; a different sensor modality needs a separately defined channel contract; the target task is unsupervised and does not use lifecycle labels; or an authoritative physical model changes the required degradation mechanism. Such a change must preserve the old rationale and explicitly version the replacement.

## IMPORTANT — Make XJTU-SY characteristic bearing frequencies configurable

**Decision:** Add `shaft_frequency_hz`, `bpfo_hz`, `bpfi_hz`, `bsf_hz`, and `ftf_hz` to the XJTU-SY FFT summary. Derive shaft frequency from `rotational_speed_rpm`. Derive BPFO, BPFI, BSF, and FTF only when a complete bearing-geometry YAML is supplied; otherwise keep those four values null and record `geometry_not_configured`. Do not invent nominal geometry values for the LDK UER204 model.

**Date:** 2026-10-09

**Problem addressed:** Frequency-domain EDA needs physically interpretable bearing fault frequencies, but the available XJTU-SY project context does not provide a verified set of rolling-element count, pitch diameter, rolling-element diameter, and contact-angle values.

**Current system state:** The FFT table is calculated at eleven lifecycle anchors and already stores the sampling rate, frequency grid, magnitude, dominant frequency, total spectral power, and band powers. The EDA now accepts an optional `--bearing-geometry` YAML configuration and records its source and configuration status in each FFT row and the EDA report.

**Business/project requirements:** Make BPFO/BPFI/BSF/FTF available for later fault-frequency analysis; preserve provenance; avoid false precision; keep the existing EDA command usable before verified geometry is available; invalidate FFT and plot caches when this configuration changes.

**Alternatives considered:** Hard-code a nominal UER204 geometry; estimate geometry from waveform peaks; omit all characteristic frequencies; or make the configuration mandatory. Hard-coding and estimation were rejected because they could attach an incorrect physical interpretation to every output. Omitting the shaft frequency loses a directly derivable quantity. Making geometry mandatory would unnecessarily block unrelated EDA work.

**Rationale:** The standard formulas use shaft frequency `fr`, rolling-element count `N`, rolling-element diameter `d`, pitch diameter `D`, and contact angle `theta`: BPFO = `N/2 * fr * (1 - (d/D) cos(theta))`, BPFI = `N/2 * fr * (1 + (d/D) cos(theta))`, BSF = `D/(2d) * fr * (1 - ((d/D) cos(theta))^2)`, and FTF = `1/2 * fr * (1 - (d/D) cos(theta))`. A supplied geometry file makes the assumptions explicit and auditable; missing geometry produces null values instead of fabricated numbers.

**Consequences:** The FFT schema has additional characteristic-frequency columns and status fields. Users must fill `configs/xjtu_bearing_geometry.example.yaml` from an authoritative bearing source before interpreting BPFO/BPFI/BSF/FTF numerically. Existing runs without that option remain valid for other FFT statistics, but must be regenerated to populate the new schema.

**Reconsideration conditions:** An authoritative XJTU-SY bearing drawing or manufacturer datasheet becomes available; shaft speed varies within a waveform and requires time-varying frequency estimates; the bearing model is confirmed to differ; or the project adopts a validated slip/geometry correction model.

## IMPORTANT — Represent each XJTU-SY bearing as a full variable-length feature trajectory

**Decision:** For Task 4.1, represent each bearing trajectory as an ordered variable-length sequence of snapshot records. Each snapshot contains the Phase 3 feature vector `X_i ∈ R^30`, `elapsed_time_sec`, the source `measurement_index`, and a feature-validity mask. Use a long Parquet table as the canonical representation, with one row per bearing × measurement snapshot. Create packed sequence arrays `[N_b, 30]`, time arrays `[N_b]`, and masks `[N_b, 30]` only as derived training artifacts; `N_b` remains variable by bearing.

Keep `measurement_index` and `elapsed_time_sec` from the source chronology. Missing measurements remain temporal gaps and are not renumbered or interpolated. Keep `split` as provenance/evaluation metadata in the table, but never include it in `X_i`. Keep condition, bearing, fault, lifetime, and other trajectory metadata outside the model feature vector; lifecycle fraction is allowed only for offline analysis/evaluation.

**Date:** 2026-10-09

**Problem addressed:** Phase 3 now produces fixed-dimensional snapshot features, but Task 4.1 needs a faithful representation of complete bearing histories before windows, anchors, targets, or model batches are created.

**Current system state:** There are 15 XJTU-SY bearing trajectories and 9,216 snapshot rows with `D = 30` features. Source measurement numbers and elapsed time follow the established XJTU chronology policy. The Phase 3 snapshot table already provides the long-table basis for this representation.

**Business/project requirements:** Preserve complete trajectories and real temporal gaps; support bearings with very different lifetimes; make the representation inspectable and reproducible; prevent lifecycle and split metadata from leaking into model inputs; support later causal history windows and variable-length future targets.

**Alternatives considered:**
1. Flatten one complete bearing into one fixed-length vector. Rejected because trajectory lengths differ substantially and the result would be impractical and hard to batch.
2. Resample or interpolate every trajectory to a common time grid. Rejected because it fabricates observations and hides missing measurements.
3. Use only a packed tensor as the canonical artifact. Rejected because a long table is easier to audit, filter, join, and reproduce; packed tensors remain useful derived training artifacts.
4. Put condition, fault, lifetime, or split identifiers into `X_i`. Rejected because these are provenance/evaluation metadata and can leak experimental structure or future information.

**Rationale:** A sequence of fixed-dimensional snapshots preserves the natural separation between per-snapshot representation and variable trajectory length. The long table retains source identity and chronology exactly, while derived arrays provide the efficient `[N_b, 30]` form required by later training code. Keeping masks and metadata separate supports incomplete channels and leakage-safe experiments without changing the raw Observation contract.

**Evidence and assumptions:** Phase 3 fixes `D = 30` by concatenating 15 horizontal and 15 vertical scalar features. The XJTU-SY project decisions require preserving numeric source measurement numbers, treating missing measurements as real gaps, avoiding waveform interpolation, and excluding lifecycle/failure information from baseline inference inputs.

**Consequences:** Task 4.1 outputs a canonical long trajectory table and may output derived per-bearing sequence artifacts. Later tasks may create causal history windows, future targets, padding masks, and batch tensors from this representation without changing its chronology. Storage and batching must handle variable `N_b`; complete trajectories must be split before those derived artifacts are created.

**Reconsideration conditions:** A future dataset requires a different atomic unit, a validated common time grid becomes necessary for a specific downstream task, or a model requires lossless multi-channel tensor packing that cannot be represented by the current derived sequence format. Any change must preserve the long-table source or introduce a versioned replacement.

## IMPORTANT — Sample causal random anchors at observed XJTU-SY snapshots

**Decision:** For Task 4.2, choose `t_anchor` only from valid observed snapshots, not from continuous times between measurements. An eligible anchor must have at least 10 valid snapshots, including the anchor snapshot, within the previous 1,800 seconds and at least one observed snapshot after the anchor. Build the eligible-anchor list separately for each complete bearing trajectory after applying the trajectory split. Sample within each bearing so long trajectories do not dominate the anchor distribution. Use deterministic seeds for validation/test and a reproducible `base_seed + epoch` policy for training. Persist an `anchor_manifest.parquet` containing the trajectory identity, split, anchor identity, source measurement index, anchor elapsed time, history/future counts, and sampling seed.

The anchor snapshot is part of the history with `lag_sec = 0`. History records use `lag_sec = elapsed_time_sec - anchor_elapsed_time_sec`; missing measurements remain temporal gaps and are not interpolated or renumbered. Task 4.2 selects anchors only; construction of history and future target sequences is a later task.

**Date:** 2026-10-10

**Problem addressed:** The full trajectory representation needs a reproducible way to select causal training/evaluation query points without fabricating timestamps, over-sampling long trajectories, or allowing anchors to cross split boundaries.

**Current system state:** Task 4.1 defines a variable-length trajectory of fixed-dimensional snapshot vectors. XJTU-SY snapshots are approximately one minute apart but may contain real missing-measurement gaps. The causal protocol requires at least 10 records from the previous 30 minutes and predicts only records after the anchor.

**Business/project requirements:** Preserve irregular chronology; create enough random query points for training; keep validation/test reproducible; give each bearing a fair opportunity to contribute; ensure every anchor has usable history and a non-empty future; prevent split and future information leakage.

**Alternatives considered:**
1. Sample arbitrary continuous times. Rejected because the anchor would not correspond to an observed feature snapshot and would require interpolation or an ambiguous current state.
2. Sample uniformly across all dataset snapshots. Rejected because long trajectories would dominate the training distribution.
3. Accept anchors with fewer than 10 history records. Rejected because the main protocol requires a minimum history; short contexts belong to a separate robustness evaluation.
4. Select anchors before applying trajectory splits. Rejected because it complicates leakage auditing and can mix split-specific artifacts.
5. Generate history and targets inside the anchor sampler. Rejected because anchor selection and sample construction should remain independently testable.

**Rationale:** Observed-snapshot anchors preserve the source time semantics and make `X_anchor` directly available. Per-bearing eligibility and sampling balance the 15 physical trajectories despite large lifetime differences. Seeded sampling gives reproducible validation/test results while allowing training diversity across epochs. Requiring a future record prevents empty targets without changing model inputs; future availability is used only for offline sample construction.

**Evidence and assumptions:** XJTU-SY records one CSV approximately every minute, the project defines `elapsed_time_sec` from the numeric source measurement, and the causal forecasting decision fixes a maximum 20-record history within 1,800 seconds with a main-protocol minimum of 10 records. The anchor does not receive lifecycle fraction, remaining life, failure time, or trajectory metadata as model input.

**Consequences:** Task 4.2 produces a reproducible anchor manifest rather than model-ready windows. Long trajectories no longer automatically contribute more anchors unless the configured per-bearing sample budget permits it. Later tasks must consume the manifest to construct history and future sequences, preserve source measurement indices, and keep all derived records within the assigned split.

**Reconsideration conditions:** A downstream task requires arbitrary query times, a validated interpolation policy becomes available, the minimum-history protocol changes, or evaluation requires a different anchor sampling design. Any change must version the anchor manifest schema and sampling policy.

### Clarification — Point 1: recent context pool versus full remaining-lifecycle target

The phrase “full lifecycle prediction” means predicting the complete remaining trajectory after `t_anchor`, not reconstructing observations before the anchor. The input context is therefore limited to at most 20 actual snapshots nearest to `t_anchor` within `[t_anchor - 1800, t_anchor]`, including the anchor and requiring at least 10 records for the main protocol. This input limit does not limit the future target: a later task may expose all observed future snapshots from immediately after the anchor through the trajectory endpoint or `END_OF_TRAJECTORY`.

### Clarification — Point 2: context-count distribution

For the main protocol, sample the integer context count as `K ~ Uniform{10, ..., min(20, pool_size)}`. `K` includes the anchor snapshot. Anchors with fewer than 10 eligible pool records are excluded from the main protocol. For a separate robustness protocol, sample `K ~ Uniform{3, ..., 9}` and label it `context_regime = short_robustness`; these short contexts are not silently mixed into main-protocol training or aggregate results.

**Rationale:** Variable `K` represents realistic differences in available monitoring history while preserving the minimum-history requirement of the main protocol. A discrete uniform distribution gives equal coverage to each supported context size, makes sensitivity by `K` measurable, and avoids letting very short contexts redefine the primary task.
