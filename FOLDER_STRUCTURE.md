# Folder structure

Directories below are physically present in the ZIP. Each pending module has a README.

```text
Meridian_Sentinel_Full_Architecture/
├── .github/
│   └── workflows/
├── apps/
│   └── web/
│       ├── public/
│       └── src/
│           ├── components/
│           ├── pages/
│           └── services/
├── config/
├── data/
│   ├── manifests/
│   ├── processed/
│   └── raw/
├── database/
│   ├── migrations/
│   ├── reference/
│   └── seeds/
├── docs/
│   └── blueprint/
│       ├── contracts/
│       ├── database/
│       ├── diagrams/
│       ├── examples/
│       └── scripts/
├── infra/
│   ├── deployment/
│   ├── docker/
│   └── observability/
├── integrations/
│   ├── cmms/
│   ├── iot/
│   ├── nasa/
│   └── notifications/
├── mcp/
│   ├── policies/
│   ├── server/
│   └── tools/
├── ml/
│   ├── calibration/
│   ├── evaluation/
│   ├── experiments/
│   ├── features/
│   └── training/
├── mlops/
│   ├── monitoring/
│   ├── registry/
│   ├── retraining/
│   ├── rollback/
│   └── tracking/
├── packages/
│   └── contracts/
├── reports/
├── runs/
│   └── fd001-v1/
├── scripts/
├── sentinel/
├── services/
│   ├── api/
│   │   └── modules/
│   │       ├── audit/
│   │       ├── auth/
│   │       ├── maintenance/
│   │       ├── predictions/
│   │       ├── registry/
│   │       └── telemetry/
│   └── worker/
│       └── jobs/
└── tests/
```

Key root files: README.md, BACKEND_QUICKSTART.md, ARCHITECTURE_OVERVIEW.md, IMPLEMENTATION_STATUS.md, AGENTS.md, requirements.txt, requirements.lock.txt, Makefile.

Original documents and rendered flowcharts: docs/blueprint/. Working Python package: sentinel/.
