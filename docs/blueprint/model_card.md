# Model Card Template

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Identity

Model name: Meridian RUL / horizon-risk candidate. Version: NOT TRAINED. Owner: ML engineer role. Intended use: C-MAPSS engine replay decision-support demonstration. Prohibited claims: validated real-plant operation, universal component diagnosis, guaranteed failure dates.

## Fill after training

Artifact ID/hash; registry URI; code commit; runtime lock; dataset/subset/hash; split IDs/seed; feature schema; operating-domain compatibility; target policy; window; horizon; calibration/interval method; thresholds; measured regression/classification/calibration/alert metrics; failure analysis; approving reviewer; release scope.

## Performance

All metrics currently **unmeasured**. Do not substitute illustrative values. Include engine-level uncertainty and operating-regime breakdown where applicable. Distinguish official final-window test from full replay policy evaluation.

## Limitations

Simulation-to-plant domain gap, noisy sensors, missing component-level labels, limited failure types, unavailable histories and uncertain preventive-intervention outcomes. Model outputs depend on applicable operating regimes and cannot establish causality. Include abstention conditions and a rollback reference.

## Review checklist

No leakage; causal features; official test untouched in tuning; compatible preprocessing; calibrated probabilities if shown; intervals evaluated if shown; release gates documented; human approval recorded. Card updated with each immutable version.
