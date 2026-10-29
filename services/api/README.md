# services/api

IMPLEMENTED ENTRYPOINT: app.py wraps the working experimental FastAPI factory in sentinel/api.py. Production registry/auth/maintenance endpoints remain pending.

Use `python -m sentinel.serve` (or `scripts/start-local.ps1`) as the canonical local
server command. It validates configuration and the model before binding loopback,
and disables access logs that could contain query strings. `app.py` remains a
compatible factory import for embedding; it is not a second implementation.
