# Cloud Public Deployment Guide (Render.com / Railway)

This guide shows you how to deploy **Meridian Sentinel** to the cloud with a **live public HTTPS URL** that you can open from any browser, phone, or computer.

---

## Method 1: Render.com (Recommended — 100% Free / Starter Tier)

Render can build and host your PostgreSQL database and the full-stack container (React UI + FastAPI + AI Models) automatically using the included `render.yaml` Blueprint.

### Step-by-Step Instructions:

1. **Sign in to Render**:
   - Go to [https://dashboard.render.com](https://dashboard.render.com) and sign in with your GitHub account (`harix28`).

2. **Create New Blueprint Instance**:
   - Click the **"New +"** button in the top navigation bar.
   - Select **"Blueprint"**.

3. **Connect Your GitHub Repository**:
   - Select the repository `harix28/flex` (or connect your GitHub if not yet authorized).
   - Render will automatically detect `render.yaml` in the root of the repository.

4. **Review & Apply**:
   - Render will show two resources to create:
     - **Database**: `meridian-db` (PostgreSQL)
     - **Web Service**: `meridian-sentinel` (Docker container using `backend/Dockerfile.public`)
   - Click **"Apply"**.

5. **Live URL Ready**:
   - Render will automatically provision PostgreSQL, run the database migrations, build the React frontend, start FastAPI, and give you a public link like:
     `https://meridian-sentinel.onrender.com`
   - You can open this link on your phone or any PC!

---

## Method 2: Railway.app (Alternative 1-Click Cloud)

1. Go to [https://railway.app](https://railway.app) and sign in with GitHub.
2. Click **"New Project"** &rarr; **"Deploy from GitHub repo"** &rarr; Select `harix28/flex`.
3. Click **"Add a Service"** &rarr; **Database** &rarr; **PostgreSQL**.
4. In the Web Service settings, set the Dockerfile path to `backend/Dockerfile.public`.
5. Under Variables, link `MIGRATION_DATABASE_URL` to `${{Postgres.DATABASE_URL}}`.
6. Railway will deploy and assign a public domain like `https://meridian-sentinel.up.railway.app`.

---

## Method 3: Cloud VPS (AWS EC2 / DigitalOcean / Hetzner)

If you have a Linux server (Ubuntu 22.04 / 24.04):

```bash
git clone https://github.com/harix28/flex.git
cd flex
./scripts/deploy.sh --dev --rebuild
```

Access your server at `http://<your-server-ip>:8080`.
