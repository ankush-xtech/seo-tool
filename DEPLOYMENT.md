# SEO Tool — Deployment Guide

Complete documentation for deploying the SEO Tool to production.

---

## Architecture Overview

```
┌─────────────────────────┐
│   Vercel (Frontend)     │  React + Vite SPA
│   seo-tool-app          │  https://seo-tool-app.vercel.app
└───────────┬─────────────┘
            │ HTTPS /api/v1
            ▼
┌─────────────────────────┐
│   Render (Backend)      │  FastAPI + Python 3.12
│   seo-tool              │  https://seo-tool-6s6i.onrender.com
└───────────┬─────────────┘
            │
            ├──────► Aiven MySQL    (primary database, SSL required)
            └──────► Upstash Redis  (rate limiting, TLS required)
```

**Note:** Celery workers are **not currently deployed**. The Maps crawling uses Python threads, and SEO checks run synchronously inside the API. Celery can be added later if bulk domain import / scheduled domain fetch features are needed.

---

## Services & Costs

| Service | Provider | Plan | Cost |
|---------|----------|------|------|
| Frontend hosting | Vercel | Hobby (Free) | $0 |
| Backend API | Render | Free (Web Service) | $0 |
| MySQL database | Aiven | Free tier | $0 |
| Redis cache | Upstash | Free tier | $0 |
| **Total** | | | **$0/month** |

**Free-tier caveats:**
- Render free tier **sleeps after 15 min idle** — first request after sleep takes ~50s to wake up
- Aiven free MySQL **auto-powers off during inactivity** — must be powered on manually or upgraded to $5/mo Basic plan
- For stable production, recommend upgrading Aiven to $5/mo (no power-off)

---

## Prerequisites

- GitHub repository: `ankush-xtech/seo-tool`
- Accounts created on:
  - [Vercel](https://vercel.com)
  - [Render](https://render.com)
  - [Aiven](https://aiven.io)
  - [Upstash](https://upstash.com)

---

## Part 1: Database — Aiven MySQL

### 1. Create the Service
1. Login to Aiven Console → **Create service** → **MySQL**
2. Choose **Free plan** (or $5/mo Basic for production)
3. Region: closest to your backend (e.g., `DigitalOcean Bangalore` or match Render's region)
4. Wait ~3 min for service to start (status: **Running**)

### 2. Allow Inbound Connections
1. Service Overview → scroll to **Allowed IP addresses**
2. Add:
   - `0.0.0.0/0` (all IPv4)
   - `::/0` (all IPv6)
3. Save — this is safe because SSL + username + password still protect the DB

### 3. Copy Connection Info
From the service **Overview** tab → **Connection information**, record:
- **Host** (e.g., `mysql-xxxx.aivencloud.com`)
- **Port** (e.g., `24281`)
- **User** (default: `avnadmin`)
- **Password** (click the eye icon to reveal)
- **Database name** (default: `defaultdb`)
- **SSL mode**: REQUIRED

### 4. Run Migrations (First Time Only)
From your local machine with `backend/.env` pointing to Aiven:

```bash
cd backend
alembic upgrade head
```

---

## Part 2: Redis — Upstash

### 1. Create the Database
1. Login to [Upstash Console](https://console.upstash.com) → **Create Database**
2. Type: **Redis**
3. Name: `redis-db`
4. Region: match your backend (e.g., `N. Virginia us-east-1` for Render Virginia)
5. Enable **TLS/SSL** (required)

### 2. Copy TCP Connection URL
In the database **Details** tab → **Connect** section → **TCP** tab:
```
rediss://default:<password>@<host>.upstash.io:6379
```

⚠️ Must start with `rediss://` (double 's' for TLS).

---

## Part 3: Backend — Render

### 1. Create Web Service
1. Render dashboard → **+ New** → **Web Service**
2. Connect GitHub repo: `ankush-xtech/seo-tool`
3. Configure:

| Field | Value |
|-------|-------|
| Name | `seo-tool` |
| Region | Virginia (US East) |
| Branch | `main` |
| Root Directory | `backend` |
| Runtime | `Docker` |
| Dockerfile Path | `./Dockerfile.prod` |
| Instance Type | Free |

### 2. Set Environment Variables

Go to **Environment** tab and add:

```bash
# ─── Aiven MySQL ───────────────────────────────
DB_HOST=mysql-xxx.aivencloud.com
DB_PORT=24281
DB_USER=avnadmin
DB_PASSWORD=<aiven-password>
DB_NAME=defaultdb
DB_SSL=true

# ─── Upstash Redis ─────────────────────────────
REDIS_URL=rediss://default:<password>@<host>.upstash.io:6379

# ─── App ───────────────────────────────────────
APP_ENV=production
APP_NAME=SEO Automation Tool
DEBUG=false
SECRET_KEY=<generate-random-64-char-string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── Admin Bootstrap ───────────────────────────
FIRST_ADMIN_EMAIL=admin@yourdomain.com
FIRST_ADMIN_PASSWORD=<strong-password>

# ─── CORS ──────────────────────────────────────
ALLOWED_ORIGINS=https://seo-tool-app.vercel.app

# ─── Optional: API Keys ────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
SERPAPI_KEY=...
DOMAINBIGDATA_API_KEY=...
```

**Best practice:** Create a Render **Environment Group** named `seo-tool-shared-env` and link it to the service — simplifies sharing env vars with future services.

### 3. Deploy
Render auto-deploys after env vars are set. Check **Logs** tab for:
```
✅ Database connected
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 4. Verify
Test the health endpoint:
```bash
curl https://seo-tool-6s6i.onrender.com/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "db": "connected",
  "env": "production"
}
```

---

## Part 4: Frontend — Vercel

### 1. Import Project
1. Vercel dashboard → **Add New** → **Project**
2. Import `ankush-xtech/seo-tool` directly (do **not** use Clone template)
3. Configure:

| Field | Value |
|-------|-------|
| Project Name | `seo-tool-app` |
| Framework Preset | Vite |
| **Root Directory** | `frontend` ⚠️ critical |
| Build Command | `npm run build` (auto-detected) |
| Output Directory | `dist` (auto-detected) |

### 2. Environment Variable
Add:
```
VITE_API_URL=https://seo-tool-6s6i.onrender.com/api/v1
```

⚠️ Must include `/api/v1` suffix — backend routes are prefixed with this.

### 3. Deploy
Click **Deploy**. Vercel builds and publishes within 1–2 min.

Live URL: `https://seo-tool-app.vercel.app`

---

## Configuration Files

### Root `vercel.json`
```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": null,
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```
Required because Vercel deploys from the repo root but the frontend is in a `frontend/` subdirectory. Also handles SPA routing.

### `frontend/vercel.json`
```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```
Used when Vercel Root Directory is set to `frontend`.

### `backend/Dockerfile.prod`
Multi-stage Docker build — produces a slim image running uvicorn with 2 workers on port 8000.

---

## Issues Encountered & Fixes

### Issue 1: Vercel 404 Not Found
**Cause:** No `vercel.json` at repo root; Vercel didn't know the frontend was in `frontend/` subdir.
**Fix:** Added root `vercel.json` pointing to the `frontend` folder.

### Issue 2: Build failed — `tsc && vite build`
**Cause:** No `tsconfig.json` in frontend; `tsc` printed help and exited with code 1.
**Fix:** Changed `frontend/package.json` build script to just `vite build` (Vite handles TS via esbuild).

### Issue 3: `AttributeError: 'str' object has no attribute 'get'`
**Cause:** SSL was being passed as URL param (`&ssl=true`) but PyMySQL requires it via `connect_args` dict.
**Fix:** Updated `backend/app/db/session.py` to pass SSL via `connect_args={"ssl": {"ssl": True}}`.

### Issue 4: `Name or service not known` (MySQL)
**Cause:** Aiven MySQL auto-powered off due to free-tier inactivity → DNS record disappeared.
**Fix:** Powered the service back on via Aiven Console. Long-term fix: upgrade to Basic $5/mo.

---

## Redeploying / Updating

### Frontend Update
```bash
git push origin main    # Vercel auto-deploys on push
```

### Backend Update
```bash
git push origin main    # Render auto-deploys on push
```

### Update Environment Variables
- **Render:** Service → Environment tab → edit → auto-redeploys
- **Vercel:** Project Settings → Environment Variables → edit → manual redeploy required

### Database Migrations
After changing models:
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head       # against local DB first
# Test locally, then:
alembic upgrade head       # against production DB (Aiven)
# Commit the migration file + push
```

---

## Monitoring & Maintenance

### Check Service Health
```bash
curl https://seo-tool-6s6i.onrender.com/api/health
```

### View Logs
- **Frontend logs:** Vercel → Deployments → click deployment → Runtime Logs
- **Backend logs:** Render → seo-tool → Logs tab
- **DB queries:** Aiven → Query statistics / Current queries
- **Redis usage:** Upstash → Data Browser / Metrics

### Keep Render Awake (Optional)
Render free tier sleeps after 15 min. To prevent:
1. Sign up at [cron-job.org](https://cron-job.org) (free)
2. Create cron: `GET https://seo-tool-6s6i.onrender.com/api/health` every 10 min

---

## Future Work

### When to Add Celery
Add Celery workers when you need:
- Bulk domain import to auto-queue SEO checks on all imported domains
- Daily scheduled domain auto-fetch at 1 AM
- Any long-running task that shouldn't block the API

Deployment options for Celery:
- **Render paid Background Worker** — $7/mo per worker
- **Fly.io** — free tier supports background workers
- Code refactor to use **FastAPI BackgroundTasks** — simpler but less scalable

### Production Checklist
- [ ] Upgrade Aiven to Basic ($5/mo) to prevent power-offs
- [ ] Upgrade Render to Starter ($7/mo) to prevent sleep
- [ ] Add custom domain on Vercel
- [ ] Set up Sentry for error monitoring (`SENTRY_DSN` env var)
- [ ] Configure SMTP for transactional emails
- [ ] Enable automated backups on Aiven
- [ ] Add Celery worker when bulk features are needed

---

## Quick Reference — Live URLs

| Service | URL |
|---------|-----|
| Frontend | https://seo-tool-app.vercel.app |
| Backend API | https://seo-tool-6s6i.onrender.com |
| API Docs | https://seo-tool-6s6i.onrender.com/api/docs |
| Health Check | https://seo-tool-6s6i.onrender.com/api/health |

---

*Last updated: 2026-04-20*
