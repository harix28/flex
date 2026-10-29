# scripts

Utility command entrypoints live in the sentinel package. See Makefile for real implemented commands.

- `start-local.ps1`: check the existing Python 3.12 environment, initialize private
  local configuration if needed, then run the canonical server in this terminal.
- `check-local.ps1`: verify the trusted FD001 bundle/data, generate the engine-1
  request under `.runtime/`, then send it to the running server.
- Both accept an optional `-Port`; otherwise they share the environment/.env port.
  Keep the startup terminal open; use a second terminal for checks. See
  `BACKEND_QUICKSTART.md` for setup, precedence, shutdown and troubleshooting.
