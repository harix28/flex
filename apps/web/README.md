# apps/web — Meridian Sentinel Frontend Portal

**Status**: IMPLEMENTED & VALIDATED (Phase 8)  
**Stack**: React 18, TypeScript 5, Vite 6, Vitest, Testing Library, Lucide Icons

---

## Overview

`apps/web` contains the web frontend portal for Meridian Sentinel. It connects to the FastAPI REST backend and PostgreSQL database to provide an interface for industrial turbofan health monitoring, causal RUL prediction, and maintenance work order lifecycles.

---

## Directory Structure

```
apps/web/
├── public/                 # Favicon, assets
├── src/
│   ├── __tests__/          # Vitest unit and integration tests
│   ├── components/
│   │   ├── charts/         # SVG SensorTrendChart (gap preservation, tabular toggle)
│   │   ├── common/         # Badge, Modal, LoadingState, EmptyState, ErrorState
│   │   ├── layout/         # Shell, Breadcrumbs
│   │   ├── predictions/    # PredictionCard, RunPredictionModal
│   │   └── work-orders/    # WorkOrderActionModal, WorkOrderCreateModal, WorkOrderNotes
│   ├── context/            # AuthContext (session, HttpOnly cookie CSRF, RBAC)
│   ├── pages/              # Overview, Machines, MachineDetail, WorkOrders, WorkOrderDetail, Registry, Members, Login
│   ├── services/           # Typed api.ts client and types.ts domain models
│   ├── test/               # Vitest jsdom setup
│   ├── App.tsx             # Hash-based SPA router and route guards
│   ├── index.css           # Industrial design system tokens & utilities
│   └── main.tsx            # React root mount
├── index.html              # HTML shell with typography and SEO metadata
├── package.json            # Dependencies and npm scripts
├── tsconfig.json           # Strict TypeScript bundler configuration
└── vite.config.ts          # Vite build config with /api and /health reverse proxy
```

---

## Quickstart

```powershell
cd apps/web
npm install

# Start Vite dev server with reverse proxy on port 5173
npm run dev -- --host 127.0.0.1 --port 5173

# Run tests
npm test

# Typecheck
npm run typecheck

# Production build
npm run build
```
