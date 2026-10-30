# Evaluation Protocol

Version: 1.0 · Updated: 2026-10-22 · Status: proposed implementation specification

## Freeze the protocol before scoring

Keep official test engines untouched until candidate selection is complete. Partition training engines, not rows/windows, into training, validation and calibration. Record seed and IDs. Use repeated grouped evaluation if the sample permits; no row-random leakage. Report FD001 separately from more complex subsets.

## Regression metrics

MAE = mean absolute RUL error; RMSE = square root of mean squared RUL error, in cycles. Official benchmark evaluation uses the final available test observation/window for each engine with its provided true RUL. Report uncapped and any capped metrics with explicit labels. Engine-bootstrap uncertainty may describe sample variability, not guarantee deployment performance.

## Classification metrics

Horizon H is fixed in cycles. Precision, recall, PR-AUC, confusion matrix, Brier score and a calibration plot. State threshold and class prevalence. ROC-AUC is optional and does not replace precision/recall for rare failures. A 95% accuracy claim alone is unacceptable.

## Alert policy evaluation

Replay held-out run-to-failure trajectories causally, one observation at a time. Define an alert episode: a persistent threshold crossing opens an episode; cooldown/deduplication keeps repeated readings in it until resolution policy. Report alerts per engine, missed engines and lead time from first actionable warning to actual failure. Distinguish pre-horizon early warnings from false alarms using a declared policy, not arbitrary labels.

## Interval evaluation

When intervals are displayed, report nominal coverage, empirical coverage, median width and regime breakdown. Calibration engines are independent. No reliability claim for unsupported regimes. Remove interval UI if the method is not evaluated.

## Decision utility

Under clearly stated synthetic costs, compare alert policies against periodic inspection and simple thresholds. This is a scenario analysis, not realized savings. Real ROI requires observed operating costs, intervention records and a defensible comparison design.

## Report template

Dataset/subset/hash; train/validation/calibration engine counts; test protocol; model/version; feature schema; target cap; horizon/threshold; metrics with units; error plots; false-alert episodes; lead-time distribution; failure cases; limitations. All actual values remain unmeasured until pipeline execution.
