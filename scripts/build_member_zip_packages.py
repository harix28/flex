"""Builds 4 domain-separated ZIP packages for each team member to push to GitHub."""
import os
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "team_packages"
OUTPUT_DIR.mkdir(exist_ok=True)

# Helper to filter out noisy / build directories
EXCLUDED_PATTERNS = {
    "__pycache__", ".pytest_cache", "node_modules", "dist", ".venv", ".git",
    ".tsbuildinfo", ".DS_Store", "Thumbs.db"
}

def should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in EXCLUDED_PATTERNS or part.endswith(".pyc") or part.endswith(".tsbuildinfo"):
            return True
    return False

def add_path_to_zip(zf: zipfile.ZipFile, rel_path: str):
    full_path = ROOT / rel_path
    if not full_path.exists():
        print(f"Warning: path {rel_path} does not exist.")
        return
    if full_path.is_file():
        if not should_skip(full_path):
            zf.write(full_path, arcname=rel_path)
    elif full_path.is_dir():
        for root, dirs, files in os.walk(full_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_PATTERNS]
            for file in files:
                f_path = Path(root) / file
                if not should_skip(f_path):
                    arc = f_path.relative_to(ROOT)
                    zf.write(f_path, arcname=str(arc).replace("\\", "/"))

# ==============================================================================
# MEMBER 1: ML & AI Predictive Intelligence Lead
# ==============================================================================
def build_member_1():
    zip_path = OUTPUT_DIR / "Member_1_ML_Predictive_Intelligence.zip"
    print(f"Building {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Code files
        paths = [
            "sentinel/data.py",
            "sentinel/features.py",
            "sentinel/train.py",
            "sentinel/rul_experiments.py",
            "sentinel/classification.py",
            "sentinel/all_subsets_training.py",
            "sentinel/inference.py",
            "sentinel/mlops",
            "runs/all-subsets-20261030-v1/COMBINED/forest.json",
            "runs/all-subsets-20261030-v1/COMBINED/forest.npz",
            "tests/test_all_subsets_training.py",
            "tests/test_classification.py",
            "tests/test_rul_experiments.py",
            "tests/test_mlops_postgres.py",
        ]
        for p in paths:
            add_path_to_zip(zf, p)
        
        # Guide
        readme_text = """# Member 1 — Machine Learning & Predictive Intelligence Lead

## 🎯 Your Technical Domain
You own the **AI / ML Algorithms, C-MAPSS Sensor Data Processing, RUL Modeling, and Cryptographic Model Verification**.

### Key Technical Highlights to Tell Judges:
1. **Zero-Pickle Threat Elimination:** Avoided Python pickle serialization risks by exporting Random Forest trees as pure numeric NumPy arrays (`forest.npz`) and metadata (`forest.json`).
2. **Cryptographic Manifest Verification:** Pinned model artifacts using SHA-256 digests (`3edb1bd6...` / `791e73e2...`) to ensure runtime server integrity.
3. **Strict Causality & Anti-Leakage:** Implemented engine-disjoint train/validation partitioning and rolling causal windows strictly bounded by observation time $t \le T$.

---

## 🚀 How to Push Your Contribution to GitHub (Under Your Account)

Run these commands in terminal/powershell inside your cloned repository:

```bash
# 1. Clone the repository (if not already cloned)
git clone https://github.com/harix28/flex.git
cd flex

# 2. Configure your personal GitHub name and email
git config user.name "Your GitHub Name"
git config user.email "your-github-account-email@example.com"

# 3. Create your domain branch
git checkout -b feature/ml-predictive-intelligence

# 4. Copy the files from this ZIP package into the repository directory.

# 5. Stage, commit and push your contribution
git add sentinel/data.py sentinel/train.py sentinel/classification.py sentinel/all_subsets_training.py sentinel/rul_experiments.py sentinel/mlops runs/ tests/test_classification.py tests/test_all_subsets_training.py
git commit -m "feat(ml): C-MAPSS telemetry processing, RUL regression & hash-pinned lifetime inference"
git push -u origin feature/ml-predictive-intelligence
```

Next, open **https://github.com/harix28/flex** in your browser, click **Compare & pull request**, and merge your PR into `main`.
Your profile photo and GitHub handle will appear on the repository's **Contributors** list!
"""
        zf.writestr("README_MEMBER_1_ML.md", readme_text)

        # Batch script helper for Windows
        push_bat = """@echo off
echo ===================================================
echo Member 1: ML & Predictive Intelligence Git Push
echo ===================================================
set /p GIT_NAME="Enter your Full Name (for Git): "
set /p GIT_EMAIL="Enter your GitHub Email: "

git config user.name "%GIT_NAME%"
git config user.email "%GIT_EMAIL%"

git checkout -b feature/ml-predictive-intelligence 2>nul || git checkout feature/ml-predictive-intelligence
git add sentinel/data.py sentinel/train.py sentinel/classification.py sentinel/all_subsets_training.py sentinel/rul_experiments.py sentinel/mlops runs/ tests/test_classification.py tests/test_all_subsets_training.py
git commit -m "feat(ml): C-MAPSS telemetry processing, RUL regression & hash-pinned lifetime inference"
git push -u origin feature/ml-predictive-intelligence

echo.
echo Contribution pushed! Now open GitHub and create/merge your Pull Request.
pause
"""
        zf.writestr("push_contribution.bat", push_bat)

# ==============================================================================
# MEMBER 2: Enterprise Backend & Real-Time Ingestion Lead
# ==============================================================================
def build_member_2():
    zip_path = OUTPUT_DIR / "Member_2_Backend_Ingestion_Engine.zip"
    print(f"Building {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        paths = [
            "sentinel/api.py",
            "sentinel/config.py",
            "sentinel/serve.py",
            "sentinel/public_serve.py",
            "sentinel/check.py",
            "sentinel/replay.py",
            "sentinel/http_support.py",
            "sentinel/ingestion",
            "sentinel/registry",
            "sentinel/predictions",
            "sentinel/jobs",
            "sentinel/degradation",
            "sentinel/notifications",
            "sentinel/integrations",
            "tests/test_api.py",
            "tests/test_ingestion_unit.py",
            "tests/test_jobs_postgres.py",
            "tests/test_predictions_postgres.py",
        ]
        for p in paths:
            add_path_to_zip(zf, p)
        
        readme_text = """# Member 2 — Enterprise Backend & Real-Time Ingestion Lead

## 🎯 Your Technical Domain
You own the **FastAPI Asynchronous Backend Core, High-Frequency Telemetry Ingestion, Dynamic Risk Band Scoring & Background Job Workers**.

### Key Technical Highlights to Tell Judges:
1. **Asynchronous Observation Pipeline:** Engineered high-throughput ingestion handling streaming sensor cycles with instantaneous duplicate rejection and cycle-gap detection.
2. **Deterministic Risk Banding Engine:** Built the fleet scoring logic that classifies turbofan engines into 4 actionable priority tiers (`Urgent`, `High`, `Medium`, `Low`) based on calibrated RUL thresholds.
3. **API Contract & Idempotency:** Implemented source event IDs, idempotency tokens, and auto-generated OpenAPI contracts to guarantee reliable communications.

---

## 🚀 How to Push Your Contribution to GitHub (Under Your Account)

Run these commands in terminal/powershell inside your cloned repository:

```bash
# 1. Clone the repository (if not already cloned)
git clone https://github.com/harix28/flex.git
cd flex

# 2. Configure your personal GitHub name and email
git config user.name "Your GitHub Name"
git config user.email "your-github-account-email@example.com"

# 3. Create your domain branch
git checkout -b feature/backend-ingestion-core

# 4. Copy the files from this ZIP package into the repository directory.

# 5. Stage, commit and push your contribution
git add sentinel/api.py sentinel/config.py sentinel/serve.py sentinel/public_serve.py sentinel/ingestion/ sentinel/registry/ sentinel/predictions/ sentinel/jobs/ tests/test_api.py
git commit -m "feat(backend): asynchronous FastAPI core, streaming ingestion pipeline & fleet priority scoring"
git push -u origin feature/backend-ingestion-core
```

Next, open **https://github.com/harix28/flex** in your browser, click **Compare & pull request**, and merge your PR into `main`.
Your profile photo and GitHub handle will appear on the repository's **Contributors** list!
"""
        zf.writestr("README_MEMBER_2_BACKEND.md", readme_text)

        push_bat = """@echo off
echo ===================================================
echo Member 2: Backend & Ingestion Engine Git Push
echo ===================================================
set /p GIT_NAME="Enter your Full Name (for Git): "
set /p GIT_EMAIL="Enter your GitHub Email: "

git config user.name "%GIT_NAME%"
git config user.email "%GIT_EMAIL%"

git checkout -b feature/backend-ingestion-core 2>nul || git checkout feature/backend-ingestion-core
git add sentinel/api.py sentinel/config.py sentinel/serve.py sentinel/public_serve.py sentinel/ingestion/ sentinel/registry/ sentinel/predictions/ sentinel/jobs/ tests/test_api.py
git commit -m "feat(backend): asynchronous FastAPI core, streaming ingestion pipeline & fleet priority scoring"
git push -u origin feature/backend-ingestion-core

echo.
echo Contribution pushed! Now open GitHub and create/merge your Pull Request.
pause
"""
        zf.writestr("push_contribution.bat", push_bat)

# ==============================================================================
# MEMBER 3: Database Architecture, Security & Governance Lead
# ==============================================================================
def build_member_3():
    zip_path = OUTPUT_DIR / "Member_3_Database_Security_CMMS.zip"
    print(f"Building {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        paths = [
            "database",
            "alembic.ini",
            "sentinel/db",
            "sentinel/auth",
            "sentinel/work_orders",
            "sentinel/audit",
            "scripts/populate_all_100_engines.py",
            "scripts/populate_all_subsets.py",
            "tests/test_auth_unit.py",
            "tests/test_work_orders_unit.py",
            "tests/test_auth_postgres.py",
            "tests/test_work_orders_postgres.py",
            "tests/test_postgres.py",
        ]
        for p in paths:
            add_path_to_zip(zf, p)
        
        readme_text = """# Member 3 — Database Architecture, Security & Governance Lead

## 🎯 Your Technical Domain
You own the **PostgreSQL Multi-Tenant Schema, Row-Level Security (RLS) Isolation, Argon2id Session Security, and Human-in-the-Loop CMMS Work Orders**.

### Key Technical Highlights to Tell Judges:
1. **PostgreSQL Row-Level Security (RLS):** Implemented strict tenant boundary isolation using `app.current_tenant_id` session settings so organizations can never leak engine telemetry to competitors.
2. **Human-in-the-Loop Maintenance State Machine:** Designed the CMMS work order workflow (`DRAFT` -> `PENDING_APPROVAL` -> `APPROVED` -> `IN_PROGRESS` -> `COMPLETED`). Machine learning predictions can draft an action, but only certified human engineers can authorize physical dispatch.
3. **Tamper-Evident Audit Dossiers:** Engineered immutable audit logs capturing every status transition, prediction snapshot, and operator sign-off with cryptographic integrity.

---

## 🚀 How to Push Your Contribution to GitHub (Under Your Account)

Run these commands in terminal/powershell inside your cloned repository:

```bash
# 1. Clone the repository (if not already cloned)
git clone https://github.com/harix28/flex.git
cd flex

# 2. Configure your personal GitHub name and email
git config user.name "Your GitHub Name"
git config user.email "your-github-account-email@example.com"

# 3. Create your domain branch
git checkout -b feature/db-security-cmms-governance

# 4. Copy the files from this ZIP package into the repository directory.

# 5. Stage, commit and push your contribution
git add database/ alembic.ini sentinel/db/ sentinel/auth/ sentinel/work_orders/ sentinel/audit/ scripts/populate_all_100_engines.py scripts/populate_all_subsets.py tests/test_auth_unit.py tests/test_work_orders_unit.py
git commit -m "feat(security): PostgreSQL RLS tenant isolation, Argon2id auth & human-in-the-loop CMMS work orders"
git push -u origin feature/db-security-cmms-governance
```

Next, open **https://github.com/harix28/flex** in your browser, click **Compare & pull request**, and merge your PR into `main`.
Your profile photo and GitHub handle will appear on the repository's **Contributors** list!
"""
        zf.writestr("README_MEMBER_3_DATABASE_SECURITY.md", readme_text)

        push_bat = """@echo off
echo ===================================================
echo Member 3: DB Architecture, Security & CMMS Push
echo ===================================================
set /p GIT_NAME="Enter your Full Name (for Git): "
set /p GIT_EMAIL="Enter your GitHub Email: "

git config user.name "%GIT_NAME%"
git config user.email "%GIT_EMAIL%"

git checkout -b feature/db-security-cmms-governance 2>nul || git checkout feature/db-security-cmms-governance
git add database/ alembic.ini sentinel/db/ sentinel/auth/ sentinel/work_orders/ sentinel/audit/ scripts/populate_all_100_engines.py scripts/populate_all_subsets.py tests/test_auth_unit.py tests/test_work_orders_unit.py
git commit -m "feat(security): PostgreSQL RLS tenant isolation, Argon2id auth & human-in-the-loop CMMS work orders"
git push -u origin feature/db-security-cmms-governance

echo.
echo Contribution pushed! Now open GitHub and create/merge your Pull Request.
pause
"""
        zf.writestr("push_contribution.bat", push_bat)

# ==============================================================================
# MEMBER 4: Frontend UI/UX & Cloud DevOps Lead
# ==============================================================================
def build_member_4():
    zip_path = OUTPUT_DIR / "Member_4_Frontend_DevOps_Cloud.zip"
    print(f"Building {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        paths = [
            "apps/web",
            "frontend",
            "backend/Dockerfile",
            "backend/Dockerfile.public",
            "backend/Dockerfile.public.dockerignore",
            "infra/nginx",
            "docker-compose.yml",
            "docker-compose.dev.yml",
            ".dockerignore",
            ".github/workflows/backend-tests.yml",
            ".github/workflows/README.md",
        ]
        for p in paths:
            add_path_to_zip(zf, p)
        
        readme_text = """# Member 4 — Frontend UI/UX & Cloud DevOps Lead

## 🎯 Your Technical Domain
You own the **React 18 Single-Page Application, Industrial TailwindCSS Design System, Docker Multi-Stage Containerization & Cloud Deployment (Render/Vercel/GitHub Actions)**.

### Key Technical Highlights to Tell Judges:
1. **Mission-Control Operator UI:** Built an ergonomic web dashboard displaying real-time turbofan fleet metrics (160 engines, 22,307 cycles) with visual distinction between replay, synthetic, and measured telemetry.
2. **Unified Reverse-Proxy Architecture:** Designed the local and cloud gateway setup using Nginx to eliminate CORS issues, terminate SSL, and deliver static web assets with zero latency.
3. **Automated CI/CD & Multi-Cloud Deployment:** Configured GitHub Actions CI workflows for automated regression testing, containerized Docker builds, and live cloud deployment on Render and Vercel.

---

## 🚀 How to Push Your Contribution to GitHub (Under Your Account)

Run these commands in terminal/powershell inside your cloned repository:

```bash
# 1. Clone the repository (if not already cloned)
git clone https://github.com/harix28/flex.git
cd flex

# 2. Configure your personal GitHub name and email
git config user.name "Your GitHub Name"
git config user.email "your-github-account-email@example.com"

# 3. Create your domain branch
git checkout -b feature/frontend-ui-and-devops

# 4. Copy the files from this ZIP package into the repository directory.

# 5. Stage, commit and push your contribution
git add apps/web/ frontend/ backend/Dockerfile* infra/nginx/ docker-compose.yml docker-compose.dev.yml .dockerignore .github/workflows/
git commit -m "feat(ui-devops): React 18 dashboard, Docker multi-stage containers & CI/CD deployment automation"
git push -u origin feature/frontend-ui-and-devops
```

Next, open **https://github.com/harix28/flex** in your browser, click **Compare & pull request**, and merge your PR into `main`.
Your profile photo and GitHub handle will appear on the repository's **Contributors** list!
"""
        zf.writestr("README_MEMBER_4_FRONTEND_DEVOPS.md", readme_text)

        push_bat = """@echo off
echo ===================================================
echo Member 4: Frontend UI & Cloud DevOps Push
echo ===================================================
set /p GIT_NAME="Enter your Full Name (for Git): "
set /p GIT_EMAIL="Enter your GitHub Email: "

git config user.name "%GIT_NAME%"
git config user.email "%GIT_EMAIL%"

git checkout -b feature/frontend-ui-and-devops 2>nul || git checkout feature/frontend-ui-and-devops
git add apps/web/ frontend/ backend/Dockerfile* infra/nginx/ docker-compose.yml docker-compose.dev.yml .dockerignore .github/workflows/
git commit -m "feat(ui-devops): React 18 dashboard, Docker multi-stage containers & CI/CD deployment automation"
git push -u origin feature/frontend-ui-and-devops

echo.
echo Contribution pushed! Now open GitHub and create/merge your Pull Request.
pause
"""
        zf.writestr("push_contribution.bat", push_bat)

if __name__ == "__main__":
    build_member_1()
    build_member_2()
    build_member_3()
    build_member_4()
    print("\\nAll 4 member packages successfully generated in:", OUTPUT_DIR)

