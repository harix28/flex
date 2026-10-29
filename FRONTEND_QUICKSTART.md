# Frontend Quickstart — Meridian Sentinel Portal (Phase 8)

This guide documents how to launch, configure, and operate the Meridian Sentinel web frontend portal locally, connected to the PostgreSQL database and FastAPI backend.

---

## 1. Prerequisites

1. **Local PostgreSQL 18 Cluster**:
   - Port `55432` (or configured port).
   - Migrated through migration `0006_work_orders`.
   - Credentials configured in `.runtime/postgres.env`.

2. **Python Virtual Environment**:
   - Python 3.12+ in `.venv`.
   - Model bundle `runs/fd001-v1` with sha256 checksum verified.

3. **Node.js Environment**:
   - Node 18+ and npm 10+ installed.
   - Working directory `apps/web/`.

---

## 2. Ports and URLs

| Service | Protocol | Host / Port | URL |
| :--- | :--- | :--- | :--- |
| **Frontend Portal** | HTTP | `127.0.0.1:5173` | [http://127.0.0.1:5173](http://127.0.0.1:5173) |
| **Backend REST Gateway** | HTTP | `127.0.0.1:8001` | [http://127.0.0.1:8001](http://127.0.0.1:8001) |
| **PostgreSQL Database** | TCP | `127.0.0.1:55432` | `meridian_dev` |

---

## 3. Demo Bootstrap / Seed Data

To provision a local demonstration organization, administrator, technician, and registered NASA C-MAPSS engine telemetry:

```powershell
.\.venv\Scripts\python.exe -m scripts.prepare_demo_data
```

This provisions:
- **Organization**: `Meridian Turbofan Maintenance` (slug `meridian-a`).
- **Administrator**: `admin@meridian.example.com` / `Password12345!` (Role: `admin`).
- **Technician**: `tech@meridian.example.com` / `Password12345!` (Role: `technician`).
- **Asset**: `NASA-FD001-TEST-1` (simulated C-MAPSS FD001 engine 1).
- **Telemetry**: 31 contiguous flight cycles ingested into `replay_observations`.

---

## 4. Starting the Local Servers

### Step A: Start Backend Server (Terminal 1)

```powershell
$env:DATABASE_URL = (Get-Content -LiteralPath .runtime/postgres.env | Where-Object { $_.StartsWith('DATABASE_URL=') }).Substring(13)
$env:SENTINEL_AUTH_ENABLED = 'true'
$env:SENTINEL_AUTH_LOCALHOST = 'true'
$env:SENTINEL_AUTH_ORIGINS = 'http://127.0.0.1:8001,http://localhost:5173,http://127.0.0.1:5173'
$env:SENTINEL_PORT = '8001'
$env:SENTINEL_HOST = '127.0.0.1'

.\.venv\Scripts\python.exe -m sentinel.serve --port 8001
```

Verify backend readiness:
```powershell
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/health/ready
```

### Step B: Start Frontend Portal (Terminal 2)

```powershell
cd apps/web
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser.

---

## 5. Frontend Development Commands

Inside `apps/web/`:

```powershell
# Run Typecheck
npm run typecheck

# Run Vitest Component/Integration Tests
npm test

# Build Production SPA Bundle
npm run build

# Preview Production Build Locally
npm run preview
```

---

## 6. Public Environment Variables

The frontend is an SPA communicating with the backend via a reverse-proxy in Vite (`vite.config.ts`) or direct CORS. 
No secrets, private keys, or API tokens are stored in the client bundle.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `""` (empty string) | Relative root, uses Vite development proxy to `http://127.0.0.1:8001` |
| `VITE_APP_TITLE` | `Meridian Sentinel` | Portal application title |

---

## 7. Shutdown Instructions

To gracefully stop local services:
1. In Terminal 2 (frontend): Press `Ctrl+C`.
2. In Terminal 1 (backend): Press `Ctrl+C`.
3. If run as background background tasks, use the `manage_task` kill action.

### Corrective browser verification

`python -m pytest -q -s scripts/verify_portal_browser.py` runs the built portal in headless Microsoft Edge against a disposable PostgreSQL database and a temporary loopback API server. Requires Playwright, Edge, a current `apps/web/dist` build and `SENTINEL_TEST_ADMIN_URL`. It creates only isolated fixture users/machines/orders and checks manager assignment, stale-version conflict, tenant switching and model monitoring. It does not reuse demo credentials or demo database records.

### Light theme
The portal now defaults to white surfaces, a soft gray background, dark text and blue actions. Shared colors live in apps/web/src/index.css; chart colors are chosen for light surfaces. Tenant/account controls wrap on mobile. Refresh the browser after updating an already-running portal.

