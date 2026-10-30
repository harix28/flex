# C-MAPSS Machine Learning & Predictive Intelligence Specification
**Author:** Raghvendra Yadav (GitHub: @2628mca0308-bit)  
**Role:** Machine Learning & Predictive Intelligence Lead  
**Domain:** C-MAPSS Sensor Analysis, RUL Regression, Lifetime Classification & Cryptographic Model Pinning  

---

## 1. Overview & Objectives
The predictive intelligence layer of Meridian Sentinel transforms high-dimensional sensor telemetry from 21 turbofan channels and 3 operational settings into actionable health stages and Remaining Useful Life (RUL) estimates.

## 2. Key Architectural Guarantees
- **Strict Causality & Anti-Leakage:** Training and validation partitions are engine-disjoint. Feature calculation uses strictly causal historical windows ($t \le T$).
- **Zero-Pickle Threat Protection:** All trained decision forest ensembles are serialized as raw, unpickled NumPy numeric arrays (`forest.npz`) paired with metadata manifests (`forest.json`).
- **Cryptographic Manifest Pinning:** Runtime model loads are verified against SHA-256 manifests (`3edb1bd6...` / `791e73e2...`) to block tampering and unauthorized weights.
- **Cross-Subset Generalization:** Ensembles are trained across NASA C-MAPSS subsets (FD001 through FD004), achieving balanced performance across single and multi-operating regime scenarios.
