# Model release and rollback

Updated 2026-10-27. This implementation manages one **local** release environment. It does not authorize production deployment, auto-promote candidates, or hot-swap a running model.

## Configure and activate

1. Verify and register a bundle with an independently trusted manifest SHA-256:

```powershell
python -m sentinel.mlops.cli register-model --model-dir runs/fd001-v1 --trusted-sha256 <trusted-sha256> --actor operator:name --reason "Reviewed baseline"
python -m sentinel.mlops.cli deploy-model --model-version fd001-v1 --model-dir runs/fd001-v1 --actor operator:name --reason "Reviewed local release"
```

2. For release-managed startup, explicitly set this in the selected environment file:

```dotenv
SENTINEL_RELEASE_POINTER=.runtime/active_release.json
```

The path is relative to that environment file. This mode works with `--env-file` and takes the model directory and bundle digest together from the pointer. Startup verifies that the pointer identifies the latest committed local desired/active deployment. An absent, stale or inconsistent pointer fails configuration. Without this setting, explicit `SENTINEL_MODEL_DIR` and `SENTINEL_BUNDLE_SHA256` remain the source of configuration; a restart does not implicitly switch them.

3. Restart through the normal local server launcher. Loading validates bundle/model/report hashes. Activation requires matching version, bundle digest, model digest and report digest. A mismatch marks the desired release failed; successful activation supersedes previous active records. An already running process is never replaced by the CLI.

## Transaction and recovery behavior

Release operations serialize using a PostgreSQL advisory lock. Desired metadata and its reconstructable pointer payload commit with the audit event before the pointer is published. A rolled-back transaction does not publish a pointer. Publication reacquires the release lock and reads the latest committed release, avoiding stale concurrent writers. File publication uses a unique temporary file and atomic replacement.

PostgreSQL and the filesystem do **not** share an atomic transaction. If the process crashes or file publication fails after commit, desired metadata remains committed. CLI failure must not be interpreted as a database rollback. Inspect status and recover the pointer before restarting:

```powershell
python -m sentinel.mlops.cli status
python -m sentinel.mlops.cli sync-release-pointer
```

Recovery regenerates the pointer from committed release audit metadata. Older deployments created before this correction lack that payload; configure a new verified local deployment first. No schema migration is required; the payload uses the existing audit JSON field. Keep runtime pointer files private and out of source control.

## Status and rollback

A desired deployment takes precedence in status reporting: `pending_restart` when a predictor is supplied, otherwise `desired_not_running`. Without a running predictor, persisted activation is reported as `recorded_active_unverified`; an offline CLI cannot prove process health. `active_untracked` means the running artifact has no matching active record.

```powershell
python -m sentinel.mlops.cli rollback-model --target-version fd001-v1 --model-dir runs/fd001-v1 --actor operator:name --reason "Reviewed rollback"
```

Rollback requires a registered model with local deployment history and verified artifacts. Rejected/archived candidates are refused. Restart in explicit pointer mode to activate the rollback. A model-load failure aborts startup; it does not automatically restart the former process or guarantee that failed activation can be recorded in an unavailable database.

## Regression checks

`tests/test_phase89_regressions.py` covers wrong-digest activation, pending restart, single active state, transaction rollback, post-commit publication failure/recovery, and explicit env-file startup with stale-pointer denial. Tests redirect pointer writes into temporary directories. Do not deploy to the real installation simply to run tests.
