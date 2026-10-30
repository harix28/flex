# Model Card: NASA C-MAPSS FD001 Turbofan RUL Regressor (`fd001-v1`)

**Author / Maintainer**: Raghvendra Yadav ([@2628mca0308-bit](https://github.com/2628mca0308-bit))  
**Model Version**: `fd001-v1`  
**Bundle SHA-256**: `06d46a9c4f5f71aeb220ade135e52e713a0bd41f362e7caf00eda743442e7cfd`  
**Feature Schema**: `cmapss-trailing-v1`  
**Status**: Hash-Pinned Production Replay Serving  

---

## 1. Model Overview

The `fd001-v1` regression model estimates the Remaining Useful Life (RUL in cycles) of high-bypass turbofan engines undergoing high-pressure compressor (HPC) degradation under sea-level static flight conditions.

```
+----------------------------------------------------------------------------------+
| Trailing Telemetry Matrix (30 cycles x 24 sensors)                               |
|   -> Window Features: [Last (24), Mean (24), Std (24), Slope (24)] (96 features) |
|   -> XGBoost Regression Trees                                                    |
|   -> Bounded RUL Output (Cycles) + Maintenance Priority Band                     |
+----------------------------------------------------------------------------------+
```

---

## 2. Intended Use & Scope

- **Primary Application**: Condition-Based Maintenance (CBM) scheduling, remaining flight hour planning, and automated work order proposal generation.
- **Out of Scope**: Direct autonomous flight shutoff or automated actuation. All maintenance recommendations pass through human inspector approval gates.
- **Operational Assumptions**:
  - Sea-level operating conditions (Single operating condition regime).
  - Single degradation mode (HPC degradation).
  - Minimum 30 consecutive operating cycles for causal window initialization.

---

## 3. Training & Validation Protocol

- **Dataset**: NASA C-MAPSS (Commercial Modular Aero-Propulsion System Simulation) Dataset `FD001`.
  - **Training Engines**: 100 run-to-failure engines ($20,631$ operating cycles).
  - **Test Engines**: 100 truncated operating histories with official ground-truth RUL.
- **Sliding Window Specification**:
  - Window length: $30$ cycles.
  - Stride: $1$ cycle.
  - Strict causality: zero future values accessible during feature extraction.
- **Target Labeling**:
  - Linear piece-wise RUL upper-bounded at $125$ cycles (early healthy plateau).

---

## 4. Benchmark Performance Metrics

Evaluated on the complete 100-engine test suite:

| Metric | Measured Value | Unit / Range |
| :--- | :--- | :--- |
| **Root Mean Squared Error (RMSE)** | **21.61** | Cycles |
| **Mean Absolute Error (MAE)** | **16.79** | Cycles |
| **Mean Absolute Percentage Error (MAPE)** | **24.48%** | % |
| **NASA Asymmetric Evaluation Score** | **1831.69** | Unitless (Lower is better) |
| **Mean Score per Engine** | **18.32** | Unitless |
| **Inference Latency (p95)** | **< 1.8 ms** | Milliseconds |

### Asymmetric Safety Penalty
NASA's asymmetric scoring function applies exponential penalties to late predictions:
$$d_i = \hat{y}_i - y_i$$
$$s_i = \begin{cases} e^{-d_i / 13} - 1 & \text{for } d_i < 0 \text{ (Safe early maintenance)} \\ e^{d_i / 10} - 1 & \text{for } d_i \ge 0 \text{ (Late / catastrophic hazard)} \end{cases}$$

Our training objective biases predictions toward safe early maintenance ($d_i \le 0$) to protect aircraft availability and passenger safety.

---

## 5. Top Predictive Sensor Channels

Feature importance analysis identifies the following primary degradation drivers:

1. **`sensor_11` (Ps30 - HPC Outlet Static Pressure)**: Strongest correlation with compressor stage deterioration.
2. **`sensor_04` (T50 - LPT Outlet Temperature)**: Reflects turbine thermal stress caused by reduced compressor efficiency.
3. **`sensor_12` (phi - Ratio of Fuel Flow to Ps30)**: Indicates specific fuel consumption increases as internal seals degrade.
4. **`sensor_09` (NRc - Corrected Core Speed)**: Core shaft deceleration under aero-thermal loading.

---

## 6. Security, Integrity & Trust Boundary

1. **No Untrusted Deserialization**: The model is serialized as native JSON/NPZ arrays. Python `pickle` loading is strictly disallowed.
2. **Cryptographic Hash Pinning**: The model bundle (`bundle.json`, `model.json`, `report.json`) must match the hardcoded SHA-256 digest on service startup.
3. **Hermetic Test Enforcement**: Any alteration of model weights or feature ordering is caught by the regression test suite.

