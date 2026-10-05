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