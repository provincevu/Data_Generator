# Project instructions

### **Persistent decision records**

Record important project decisions so that their reasoning and context remain available independently of chat history.

- Record decisions when they are made, especially decisions where the user has been deeply involved or has provided substantial direction. Such decisions should be explicitly marked as **important**.
- Each decision record should include:
  - **Decision:** a brief description of what was decided.
  - **Date:** when the decision was made.
  - **Problem addressed:** the problem or question that led to the decision.
  - **Current system state:** the relevant state of the system at the time of the decision.
  - **Business requirements:** the underlying business or project requirements motivating the decision.
  - **Alternatives considered:** the meaningful alternatives that were evaluated.
  - **Rationale:** why this option was selected, including:
    - the criteria used to evaluate the alternatives;
    - the reasoning and arguments supporting the decision;
    - the assumptions underlying the decision;
    - the evidence supporting those arguments and assumptions.
  - **Consequences:** the expected positive and negative consequences of the decision.
  - **Reconsideration conditions:** the conditions or circumstances under which the decision may no longer be appropriate and should be reviewed.
- Do not record decisions merely as conclusions. Preserve enough context to understand **why** the decision was made and **when it should be reconsidered**.
- When a decision changes, update its record rather than silently superseding it elsewhere in code, experiments, or documentation.
- If a decision appears unreasonable, outdated, or inconsistent with the project's current needs, discuss and review it before changing the durable decision record.
- Record project decisions in `docs/decisions.md`.
- Before taking an action that may be affected by a previous decision, review the relevant entries in `docs/decisions.md` first. Ensure that the planned action does not unintentionally conflict with decisions made previously.
- Also update the Vietnamese version of the decision records in `docs/decisions_vi.md` for easier reading.
- If the planned action appears to conflict with an existing decision, do not silently override the previous decision. Review the conflict, discuss whether the decision should be changed, and update both `docs/decisions.md` and `docs/decisions_vi.md` when the decision is formally revised.

### **Response requirements**
- When responding to me, limit the use of confusing English terms (you may still use English terms if translating them into Vietnamese would result in a loss of meaning). For me, a good conversation is one where both parties understand each other's intent.

### **Mandatory lifecycle-generation requirements**

Before taking any action that implements, edits, tests, reviews, or interprets a lifecycle-data generator, synthetic vibration data, RUL, health index, degradation stages, or failure-prediction labels, read:

- `docs/lifecycle_generation_requirements.md`
- `docs/lifecycle_generation_requirements_vi.md`
- the relevant entries in `docs/decisions.md` and `docs/decisions_vi.md`

These requirements are mandatory, not suggestions. The Agent must verify all five requirements—clear healthy/FPT/degradation/EOL progression, physically meaningful time/frequency evolution with periodic impacts, synchronized RUL/HI labels, stochastic variability with reproducible seeds, and consistent multi-sensor channels—before making or approving a change. If a change intentionally violates one of them, stop and record or review an explicit decision in both decision files before continuing.
### **XJTU-SY dataset instructions and durable context**

Before performing any task that reads, transforms, labels, analyzes, splits, or models XJTU-SY data, the Agent must read:

- `data/raw/XJTU-SY_Bearing_Datasets/Data/XJTU-SY_Bearing_Datasets/Introduction_to_XJTU-SY_Bearing_Dataset.pdf`
- the relevant entries in `docs/decisions.md` and `docs/decisions_vi.md`

The PDF is the source of dataset facts. The exact Table 2 values are preserved in `docs/xjtu_dataset_reference.md`; read that reference before implementing XJTU metadata. It is evidence and documentation, not a replacement for project decisions. If a project decision differs from a simplifying assumption in the PDF, follow the project decision and preserve the distinction in documentation.

Important dataset facts from the PDF:

- XJTU-SY contains 15 rolling-element bearings with complete run-to-failure trajectories.
- There are three operating conditions, with five bearings per condition:
  - condition 1: 2100 rpm (35 Hz), 12 kN;
  - condition 2: 2250 rpm (37.5 Hz), 11 kN;
  - condition 3: 2400 rpm (40 Hz), 10 kN.
- The tested bearing model is LDK UER204.
- Two PCB 352C33 accelerometers are mounted at 90 degrees, producing horizontal and vertical channels.
- The documented sampling frequency is 25.6 kHz. The documented recording window is 32,768 samples (1.28 seconds), repeated every 1 minute.
- Each sampling is stored as a CSV; the first column is horizontal vibration and the second column is vertical vibration.
- Table 2 documents, for each bearing, the number of CSV files, reported lifetime, and fault element.
- The test is described as continuing until the maximum horizontal or vertical amplitude exceeds 10 * A_h, where A_h is the maximum amplitude during the normal operating stage.
- The PDF distinguishes fault elements in Table 2 from failure appearances such as inner-race wear, cage fracture, outer-race wear, and outer-race fracture in the figures.

Project conventions that must also be preserved:

- A numeric filename `n.csv` is source measurement `n`; do not renumber measurements after gaps.
- For the canonical Observation layer, use `elapsed_time_sec = (measurement_index - 1) * 60`. This uses source measurement 1 as the time origin; a missing measurement 1 must not be silently collapsed.
- The raw parser keeps the actual waveform length and raw samples. The documented 32,768 samples are an expected value, not a hard rejection rule for this project.
- A missing measurement is a real temporal gap. Local repair of a small number of waveform samples, if ever approved, belongs to a separate preprocessing layer and must not overwrite raw data.
- The canonical raw Observation contract is one record per bearing x measurement x channel. Do not combine horizontal and vertical channels into one raw waveform.
- `terminal_fault_type` or normalized fault-element metadata is trajectory-level metadata. Do not invent timestamp-level `fault_state` labels from the PDF.
- Preserve both the source fault label (`fault_element_raw`) and any normalized multi-label representation (`fault_elements`). Do not silently merge fault element labels with failure morphology labels.
- Keep reported lifetime from the PDF separate from normalized Observation elapsed time. Do not replace one with the other without a documented decision.
- Condition, bearing, channel, sampling, lifetime, and fault metadata must retain their source path or citation and confidence/provenance where applicable.

When a task would change any of these rules, review the conflict first and update both decision records before implementing the change.
