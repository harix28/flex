# Sources and scope

Reviewed 2026-10-22:
- NASA dataset and description: https://data.nasa.gov/dataset/cmapss-jet-engine-simulated-data
- Original archive: https://data.nasa.gov/docs/legacy/CMAPSSData.zip
- XGBoost native model serialization: https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html
- User supplied `Meridian_Sentinel_Documentation(1).zip`: PRD, architecture, Models, data_pipeline, evaluation, data_contracts and AGENTS instructions.

NASA archive README and parser agree on **26 total columns**: ID + cycle + 3 settings + 21 sensor measurements. The README's final 'sensor measurement 26' text is an indexing typo, not 26 sensors. We retain generic sensor aliases and native data values; no invented physical unit labels.

FD001: single operating condition, HPC degradation. FD002: six conditions, HPC degradation. FD003: single condition, fan/HPC degradation. FD004: six conditions, fan/HPC degradation. These are dataset background modes, not per-observation learned diagnoses.

Original training trajectories run to failure. Official test trajectories end before failure and have a separate RUL label vector. Training labels = last training cycle minus current cycle; test labels attach only to the final observed test window for each engine.
