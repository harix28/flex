# Meridian Sentinel — Model Monitoring & Evaluation Guide

Version: 1.0 · Updated: 2026-10-26 · Scope: Input Drift & Ground-Truth Performance

---

## 1. Input Feature Drift Monitoring

Input drift monitoring measures whether recent operating inputs received by the model have shifted significantly compared to the baseline distribution on which the model was trained.

### 1.1 Reference Profile Provenance
- **Source Dataset**: NASA C-MAPSS `train_FD001.txt` (SHA-256: `963b5e22825b34d8b21c69e1aeb4af3e647050eb672ee8834ba4b5d91d2de0f8`).
- **Engine Partition**: Strictly the 70 engines identified in `report.json['split']['train']`. Validation engines (15 engines), calibration engines (15 engines), and test engines are **excluded** to prevent data leakage and reference pollution.
- **Window Count**: Exactly 12,377 causal sliding windows of length 30 cycles.
- **Feature Space**: 96 features extracted using the shared causal feature pipeline (`sentinel.features`).

### 1.2 Constant Feature Treatment
In C-MAPSS subset FD001, exactly **28 features** have zero sample variance ($\sigma < 10^{-6}$) across all 12,377 training windows:
- Operating setting 3: `setting_3`, `setting_3__std`, `setting_3__trend`, `setting_3__min`, `setting_3__max`.
- Non-varying sensors: `sensor_01`, `sensor_05`, `sensor_10`, `sensor_16`, `sensor_18`, `sensor_19` and their statistical derivatives (`std`, `trend`, `min`, `max`).

**Handling Rule**:
- Constant features are explicitly excluded from standard z-score calculations ($z = \frac{\mu - \mu_{ref}}{\sigma_{ref}}$) to prevent division by zero.
- Constant features are checked for strict deviation ($|\mu - \mu_{ref}| > 10^{-4}$). Any shift in a constant feature is flagged as a regime shift.
- Standard z-score tests are evaluated across the remaining 68 varying features.

### 1.3 Sample Thresholds & Deduplication
- **Deduplication**: Inferences are deduplicated by `input_digest` (SHA-256 of window observations) to prevent repeated polling of the same sensor state from inflating sample volume.
- **Threshold**: Requires a minimum of **5 unique input windows** (`min_samples=5`). If fewer unique samples exist, the monitor returns `status='insufficient_data'` with an explicit diagnostic message.

### 1.4 Interpretation & Regulatory Disclaimer
> **CRITICAL DISCLAIMER**: Drift is statistical evidence of shifted sensor input distributions relative to training conditions. It is **NOT** proof that predictions are inaccurate, nor is it proof that an engine or physical component has failed.

---

## 2. Ground-Truth Performance Evaluation

Evaluating prediction accuracy requires verified true outcomes (remaining useful life).

### 2.1 The In-Flight Ground-Truth Reality
In operating physical aviation and industrial manufacturing:
- **No Ground Truth in Flight**: An operating aircraft turbofan does not transmit its true remaining useful life until failure or disassembly occurs.
- **Work Orders are Not Ground Truth**: A completed maintenance work order or technician sign-off represents an operational or scheduling decision, **not** verified component degradation ground truth. Work orders must never be used to train models or measure live accuracy.
- **Live Fleet Accuracy**: Consistently reported as **UNAVAILABLE**.

### 2.2 Offline Replay Evaluation with Verified Labels
Accuracy is evaluated offline by joining predictions against verified ground-truth reference labels (`data/raw/RUL_FD001.txt`).

#### Verification & Joining Rules:
1. **Label Checksum Verification**: Reference labels must match the verified SHA-256 hash (`a19c8ec94931949d0485bdc35118206e9c81c4547b422efb9cf86f4ceddbceca`).
2. **Deterministic Join**: Joined strictly by `tenant_id`, `machine_id`, `subset='FD001'`, and `split='test'`.
3. **RUL-at-Cutoff Calculation**:
   For official test engines evaluated prior to the final cycle:
   $$\text{RUL}_{\text{actual}}(c) = \text{RUL}_{\text{final}} + (t_{\text{max}} - c)$$
   where $\text{RUL}_{\text{final}}$ is the official reference label, $t_{\text{max}}$ is the maximum recorded test cycle for that engine, and $c$ is the requested prediction cutoff cycle.

### 2.3 Evaluated Metrics
- **Mean Absolute Error (MAE)**: $\frac{1}{N} \sum | \hat{y}_i - y_i |$ cycles.
- **Root Mean Squared Error (RMSE)**: $\sqrt{\frac{1}{N} \sum (\hat{y}_i - y_i)^2}$ cycles.
- **Mean Signed Error (Bias)**: $\frac{1}{N} \sum (\hat{y}_i - y_i)$ cycles. Positive bias indicates systematic overestimation of remaining life (conservative risk).
- **Overestimation Rate**: Fraction of predictions where $\hat{y}_i > y_i$.
- **Mean Overestimation Magnitude**: Average overestimation error among overestimating predictions.

### 2.4 Protocol Separation
- `official_test_final_cutoff`: Evaluates exactly one prediction per engine at its final observed test cycle ($c = t_{\text{max}}$). Matches the official NASA benchmark protocol.
- `multi_cutoff_trajectory`: Evaluates intermediate cutoffs along an engine's degradation history. Intermediate evaluations must never be pooled with final cutoffs and called independent engines.

## Phase 8–9 corrections (2026-10-27)

Ground-truth evaluation verifies the model manifest/report and the hashes of both the complete matching test trajectory file and its RUL labels. Place the verified `test_FD001.txt` alongside `RUL_FD001.txt`. The endpoint comes from the complete verified source, not the latest ingested cycle. For FD001 test engine 1, cutoff 30 has true RUL 113 because the source ends at 31 with final RUL 112. Ingesting cycle 31 later must not change evaluation of cutoff 30. Stream file hashes must match; incompatible source/model/partition references are rejected. Empty matching-machine sets persist `insufficient_data`.

The current CLI defaults to the trusted FD001 baseline. Unsupported model versions are rejected for evaluation or reported as `incompatible_reference` for drift; a version string alone does not select a new reference. Service callers providing another model must supply its explicit directory and trusted manifest digest.

Drift profile cache reuse requires verified model/report/data identity, training engine IDs, ordered feature names and window size. Missing or incompatible caches are rebuilt from verified training data; cached content never bypasses model/data verification. Reported drift remains a statistical input comparison, not a physical-health assessment or an automatic release gate.
