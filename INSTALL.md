# Milestone 6 — Production Deploy
# Complete Installation & Deployment Guide

## What's in M6

  backend/app/main.py              REPLACE — Sentry integration, global error handler, prod API docs disabled
  backend/app/core/config.py       REPLACE — SENTRY_DSN optional field added
  backend/Dockerfile.prod          NEW — Multi-stage prod Docker image (non-root user, healthcheck)
  backend/.env.production          NEW — Production env template

  frontend/Dockerfile.prod         NEW — Multi-stage build: Node build → Nginx serve
  frontend/nginx-spa.conf          NEW — Nginx SPA config (serves index.html for all routes)

  nginx/nginx.conf                 NEW — Main Nginx config (security headers, rate limiting, gzip)
  nginx/conf.d/app.conf            NEW — Site config (HTTP→HTTPS redirect, API proxy, SSL)

  mysql/mysql.cnf                  NEW — MySQL production tuning

  docker-compose.yml               REPLACE — Clean dev compose with named containers
  docker-compose.prod.yml          NEW — Full production compose stack

  .env.production                  NEW — Root-level compose env template

  .github/workflows/ci-cd.yml      NEW — GitHub Actions: test → build → push → deploy

  scripts/setup-server.sh          NEW — One-time Ubuntu 22.04 VPS setup
  scripts/init-ssl.sh              NEW — Let's Encrypt SSL certificate initialization
  scripts/backup-db.sh             NEW — Daily MySQL backup with optional S3 upload
  scripts/health-check.sh          NEW — Service health monitoring script

---

## HOW TO INSTALL (Local Dev — Quick)

### Step 1 — Copy all M6 files
Copy all files/folders from this patch into your seo-tool/ project root.
Replace when asked.

### Step 2 — Restart normally (no change for local dev)
  uvicorn app.main:app --reload    (backend terminal)
  npm run dev                      (frontend terminal)

---

## HOW TO DEPLOY (Production VPS)

### Requirements
  - Ubuntu 22.04 VPS (min 2 CPU, 4GB RAM, 40GB disk)
  - Domain name with DNS A record pointing to your VPS IP
  - GitHub account (for CI/CD)

### Step 1 — First-time server setup
SSH into your VPS as root, then:

  wget https://raw.githubusercontent.com/YOUR_USER/YOUR_REPO/main/scripts/setup-server.sh
  sudo bash setup-server.sh yourdomain.com your@email.com

This installs: Docker, Docker Compose, UFW firewall, Fail2Ban.

### Step 2 — Clone your repo on the server

  git clone https://github.com/YOUR_USER/YOUR_REPO.git /opt/seo-automation
  cd /opt/seo-automation

### Step 3 — Configure environment files

  # Root-level compose env
  cp .env.production .env.prod.local
  nano .env.prod.local
  # Set: DB_ROOT_PASSWORD, DB_PASSWORD, REDIS_PASSWORD, VITE_API_URL

  # Backend app env
  cp backend/.env.production backend/.env.prod.local
  nano backend/.env.prod.local
  # Set: SECRET_KEY (run: openssl rand -hex 32)
  # Set: DB_PASSWORD, SMTP settings, FIRST_ADMIN_EMAIL/PASSWORD
  # Optional: SENTRY_DSN (from sentry.io)

### Step 4 — Get SSL certificate (first time only)

  bash scripts/init-ssl.sh yourdomain.com your@email.com

### Step 5 — Update Nginx config with your domain

  nano nginx/conf.d/app.conf
  # Replace "yourdomain.com" with your actual domain (3 places)

### Step 6 — Start the production stack

  docker-compose -f docker-compose.prod.yml --env-file .env.prod.local up -d

### Step 7 — Run database migrations

  docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

### Step 8 — Verify everything works

  bash scripts/health-check.sh

  # Expected output:
  # [OK]   FastAPI (200)
  # [OK]   Nginx HTTP (200)
  # [OK]   MySQL (running)
  # [OK]   Redis (running)
  # [OK]   API (running)
  # [OK]   Worker (running)
  # [OK]   Beat (running)
  # [OK]   Frontend (running)
  # [OK]   Nginx (running)
  # [OK]   Disk usage: XX%
  # All checks passed.

---

## CI/CD SETUP (GitHub Actions)

### Step 1 — Add GitHub Secrets
Go to your repo → Settings → Secrets → Actions → New repository secret:

  PROD_HOST        Your VPS IP address
  PROD_USER        SSH username (usually ubuntu or root)
  PROD_SSH_KEY     Your private SSH key (run: cat ~/.ssh/id_rsa)

### Step 2 — Push to main branch
Every push to main automatically:
  1. Runs backend lint + DB migration test
  2. Runs frontend TypeScript check + build
  3. Builds and pushes Docker images to GitHub Container Registry
  4. SSHes into your VPS and deploys

---

## DATABASE BACKUP (Cron)

Add to crontab on your VPS (run: crontab -e):

  # Daily backup at 2:00 AM
  0 2 * * * DB_ROOT_PASSWORD=yourpassword bash /opt/seo-automation/scripts/backup-db.sh >> /var/log/seo-backup.log 2>&1

For S3 upload, add:
  0 2 * * * DB_ROOT_PASSWORD=yourpassword BACKUP_S3_BUCKET=your-bucket-name bash /opt/seo-automation/scripts/backup-db.sh

---

## MONITORING

### Health checks every 5 minutes:
  */5 * * * * bash /opt/seo-automation/scripts/health-check.sh >> /var/log/seo-health.log 2>&1

### View logs:
  docker-compose -f docker-compose.prod.yml logs -f api
  docker-compose -f docker-compose.prod.yml logs -f worker
  tail -f backend/logs/celery_worker.log

### Restart a single service:
  docker-compose -f docker-compose.prod.yml restart api
  docker-compose -f docker-compose.prod.yml restart worker

---

## PRODUCTION CHECKLIST

Before going live, confirm these are done:

  [ ] SECRET_KEY is a strong random 32+ char string
  [ ] DB_PASSWORD is strong (not "seo_password")
  [ ] REDIS_PASSWORD is set
  [ ] FIRST_ADMIN_PASSWORD is changed from default
  [ ] yourdomain.com replaced in nginx/conf.d/app.conf
  [ ] SSL certificate obtained and working
  [ ] SMTP configured for email alerts
  [ ] SENTRY_DSN set (optional but recommended)
  [ ] DB backup cron added
  [ ] Health check cron added
  [ ] Swagger docs disabled in production (automatic when APP_ENV=production)
  [ ] GitHub Actions secrets set (PROD_HOST, PROD_USER, PROD_SSH_KEY)
