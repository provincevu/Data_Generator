# XJTU-SY dataset reference

This document records source facts extracted from `data/raw/XJTU-SY_Bearing_Datasets/Data/XJTU-SY_Bearing_Datasets/Introduction_to_XJTU-SY_Bearing_Dataset.pdf`. It is a reference, not a replacement for the canonical project decisions.

## Source facts

- Provider: Xi'an Jiaotong University and Changxing Sumyoung Technology.
- Tested bearing model: LDK UER204.
- Sensor: two PCB 352C33 accelerometers at 90 degrees; horizontal and vertical channels.
- Sampling frequency: 25.6 kHz.
- Recorded window: 32,768 samples, 1.28 seconds, repeated every 1 minute.
- One CSV is saved for each sampling; column 1 is horizontal vibration and column 2 is vertical vibration.
- Experiments continue until the maximum horizontal or vertical amplitude exceeds 10 * A_h, where A_h is the maximum amplitude during normal operation.

## Table 2 metadata

| Condition | Bearing | CSV files | Reported lifetime | Fault element |
|---|---|---:|---:|---|
| condition_1 / 35 Hz / 12 kN | Bearing1_1 | 123 | 2 h 3 min | Outer race |
| condition_1 / 35 Hz / 12 kN | Bearing1_2 | 161 | 2 h 41 min | Outer race |
| condition_1 / 35 Hz / 12 kN | Bearing1_3 | 158 | 2 h 38 min | Outer race |
| condition_1 / 35 Hz / 12 kN | Bearing1_4 | 122 | 2 h 2 min | Cage |
| condition_1 / 35 Hz / 12 kN | Bearing1_5 | 52 | 52 min | Inner race and outer race |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_1 | 491 | 8 h 11 min | Inner race |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_2 | 161 | 2 h 41 min | Outer race |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_3 | 533 | 8 h 53 min | Cage |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_4 | 42 | 42 min | Outer race |
| condition_2 / 37.5 Hz / 11 kN | Bearing2_5 | 339 | 5 h 39 min | Outer race |
| condition_3 / 40 Hz / 10 kN | Bearing3_1 | 2538 | 42 h 18 min | Outer race |
| condition_3 / 40 Hz / 10 kN | Bearing3_2 | 2496 | 41 h 36 min | Inner race, ball, cage and outer race |
| condition_3 / 40 Hz / 10 kN | Bearing3_3 | 371 | 6 h 11 min | Inner race |
| condition_3 / 40 Hz / 10 kN | Bearing3_4 | 1515 | 25 h 15 min | Inner race |
| condition_3 / 40 Hz / 10 kN | Bearing3_5 | 114 | 1 h 54 min | Outer race |

## Interpretation rules for this project

- `fault_element` is trajectory-level metadata, not a timestamp-level `fault_state` label.
- Preserve the PDF wording in `fault_element_raw`; if normalized labels are created, store them separately as a list such as `fault_elements`.
- Keep the reported lifetime separate from Observation `elapsed_time_sec`.
- The PDF documents the expected 32,768-sample window. The project raw parser still preserves actual waveform length and does not reject a file solely for a small length difference.
- The numeric CSV filename remains the source measurement number. The project convention is `elapsed_time_sec = (measurement_index - 1) * 60`.

## Source

`data/raw/XJTU-SY_Bearing_Datasets/Data/XJTU-SY_Bearing_Datasets/Introduction_to_XJTU-SY_Bearing_Dataset.pdf`