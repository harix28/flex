# Explicit demo seed

Run `python -m sentinel.db seed-demo` after upgrading (optionally pass
`--env-file .runtime/postgres.env`). See [operations](../README.md).
The transaction inserts deterministic SAMPLE-labelled tenant, user, inactive viewer
membership, machine, sensor and installation records. Repeated runs preserve existing
records through primary-key conflict handling; genuine conflicting codes fail and
roll back. No default/shared password, active login or production bypass is supplied.
