# Database Architecture, Security & CMMS Governance Specification
**Author:** Sanjana Tiwari (GitHub: @Sanjana-tiwari-9695)  
**Role:** Database Architecture, Security & Governance Lead  
**Domain:** PostgreSQL Multi-Tenancy, Row-Level Security (RLS), Argon2id Session Security & CMMS Work Orders  

---

## 1. Overview & Objectives
This domain ensures zero tenant data leakage, robust role-based access control, and human-in-the-loop operational safety for maintenance dispatch.

## 2. Key Architectural Guarantees
- **PostgreSQL Row-Level Security (RLS):** Database policies enforce strict tenant boundaries via `app.current_tenant_id` session configuration. Non-privileged roles (`sentinel_app`) cannot read or write across tenant boundaries.
- **Argon2id Password Hashing & CSRF Protection:** Cryptographically secure credential verification with per-user salts, timing-safe comparisons, and mandatory CSRF tokens on mutating requests.
- **Human-in-the-Loop CMMS State Machine:** Work orders progress through strict finite states (`DRAFT` -> `PENDING_APPROVAL` -> `APPROVED` -> `IN_PROGRESS` -> `COMPLETED`). Machine learning predictions can draft recommendations, but cannot auto-approve physical dispatches.
- **Tamper-Evident Audit Dossiers:** Cryptographic audit logging captures every state change, operator identifier, and prediction snapshot.
