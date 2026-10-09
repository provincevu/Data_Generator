# Core lifecycle data-generation requirements

**Status:** mandatory project requirements. Read this document before implementing, editing, testing, or interpreting any lifecycle-data generator, synthetic vibration data, RUL, health-index, degradation-stage, or failure-prediction task.

These requirements define the minimum behavior of lifecycle data produced for supervised AI models. A generator must not be considered complete merely because it produces waveforms.

## 1. Clear health-stage progression

Every lifecycle must expose a healthy phase, a first-predicting time (FPT), a degradation phase, and an end-of-life (EOL). The healthy phase must contain stable mechanical background noise rather than a hidden degradation trend. The transition at FPT must be gradual and physically plausible, not a single discontinuous amplitude jump. FPT and EOL must be stored as lifecycle metadata and be recoverable for every generated sample.

## 2. Physically meaningful time- and frequency-domain evolution

The generator must not create degradation by multiplying a healthy waveform by an ever-growing amplitude alone. It must change signal structure in both domains:

- Time-domain statistics must evolve nonlinearly. RMS and peak may grow with a nonlinear law; kurtosis should usually rise when impacts first become detectable, then may fall slightly or plateau as damage spreads. The exact curve must remain configurable and auditable.
- Frequency-domain content must contain physically motivated fault components: BPFO, BPFI, BSF, or FTF when bearing geometry and speed are known, plus shaft-related sidebands where appropriate. Periodic impact trains and a resonant response must be injected into the healthy background, with energy at characteristic frequencies increasing through degradation.
- If geometry or calibration is unavailable, the output must say so explicitly; the generator must not silently invent physical frequencies.

## 3. Automatically synchronized targets

Each generated sample must receive labels from the same lifecycle state used to generate its waveform:

- Piecewise-linear normalized RUL remains `1.0` through the healthy phase and decreases linearly from `1.0` at FPT to `0.0` at EOL.
- Health Index (HI) is continuous, starts at `1.0`, and decreases toward `0.0` as damage progresses.
- At minimum, output metadata must identify lifecycle ID, sample/time index, FPT, EOL, health stage, RUL, and HI. Labels must be generated from one shared source of truth, not reconstructed later from filenames.

## 4. Stochastic variability

Different lifecycles must not be identical copies. Lifetime and, where appropriate, FPT must vary using a documented Weibull, log-normal, or equivalent distribution. Degradation rate, impact strength, resonance, load/environment noise, and observation noise must vary by lifecycle. Curves may fluctuate and temporarily recover; strict monotonicity is not required for raw measurements. Every lifecycle must record its random seed and generation parameters so it can be reproduced.

## 5. Multi-sensor consistency

Horizontal and vertical channels must share the same lifecycle clock, FPT, EOL, and latent health trajectory. Their energy, phase, resonance, noise, and impact visibility may differ according to sensor orientation and load. The generated representation must support an input shape of `(time_steps, channels)` and must never create contradictory health labels between channels from the same physical time step.

## Required review questions

Before accepting a generator change, verify that the change preserves all five requirements, keeps FPT/EOL and labels synchronized, retains provenance of physical assumptions, and records seed/configuration information. Any intentional exception requires an explicit decision record in `docs/decisions.md` and `docs/decisions_vi.md`.
