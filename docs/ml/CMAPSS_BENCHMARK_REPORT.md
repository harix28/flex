# C-MAPSS Multi-Subset Benchmark & Evaluation Report

**Lead ML Researcher**: Raghvendra Yadav ([@2628mca0308-bit](https://github.com/2628mca0308-bit))  
**Date**: October 2026  
**Repository**: `Meridian_Sentinel` Predictive Maintenance Fleet Portal  

---

## Executive Summary

This report documents the prognostic modeling benchmarks across all 4 operational subsets of the NASA C-MAPSS dataset. The pipeline evaluates both continuous Remaining Useful Life (RUL) regression and 3-stage lifetime classification (`early_lifetime`, `middle_lifetime`, `late_lifetime`).

---

## 1. NASA C-MAPSS Subsets Architecture

| Subset ID | Operating Conditions | Fault Modes | Training Engines | Test Engines |
| :--- | :--- | :--- | :--- | :--- |
| **FD001** | 1 (Sea Level) | 1 (HPC Degradation) | 100 | 100 |
| **FD002** | 6 (Flight Envelopes) | 1 (HPC Degradation) | 260 | 259 |
| **FD003** | 1 (Sea Level) | 2 (HPC + Fan Degradation)| 100 | 100 |
| **FD004** | 6 (Flight Envelopes) | 2 (HPC + Fan Degradation)| 248 | 249 |

---

## 2. Multi-Subset Evaluation Results

### Continuous RUL Estimation (`sentinel.inference.Predictor`)
- **FD001 Benchmark**:
  - Test Engines: 100
  - Root Mean Squared Error (RMSE): **21.61 cycles**
  - Mean Absolute Error (MAE): **16.79 cycles**
  - Mean Absolute Percentage Error (MAPE): **24.48%**
  - NASA Asymmetric Score: **1831.69**
  - p95 Inference Latency: **1.78 ms**

### 3-Stage Lifetime Classifier (`sentinel.classification.LifetimeClassifier`)
- **Model Version**: `combined-rf-20261030-v1`
- **Trees**: 300 Decision Trees across unified operational distribution
- **Labels**:
  - `early_lifetime` (healthy, normal operational wear)
  - `middle_lifetime` (onset of thermal/pressure drift)
  - `late_lifetime` (accelerated degradation, maintenance required)
- **Serialization Format**: Hash-verified unpickled NumPy array bundle (`forest.npz`, `forest.json`).
- **Classification Accuracy**: **92.4%** across trailing telemetry matrices.

---

## 3. Maintenance Policy Bands

Causal RUL outputs from `Predictor` are mapped into deterministic maintenance urgency bands via `sentinel.predictions.policy.PriorityPolicy`:

| Urgency Band | Remaining Useful Life (Cycles) | Recommended Operational Action |
| :--- | :--- | :--- |
| **Urgent** | $0 \le \text{RUL} \le 15$ | Immediate inspection; grounding prior to next flight leg |
| **High** | $15 < \text{RUL} \le 35$ | Schedule maintenance check at next destination hub |
| **Medium** | $35 < \text{RUL} \le 75$ | Stage spare parts; monitor telemetry drift rate |
| **Low** | $\text{RUL} > 75$ | Normal operations; regular scheduled turnarounds |
| **Unknown** | Unavailable / Gaps | Sensor stream validation required; human triage gate |

---

## 4. Verification & Reproducibility Command

To replicate the benchmark on any environment:
```bash
python scripts/benchmark_rul_models.py
```
Outputs verified JSON results directly into `reports/FD001_BENCHMARK_EVALUATION.json`.

