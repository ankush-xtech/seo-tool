# Milestone 5 — Alerts, Notifications & Reporting
# Patch Install Instructions

## What's new in M5

### Backend — New Files
  backend/app/routers/alerts.py              Alert rules CRUD + notification endpoints
  backend/app/routers/reports.py             CSV export endpoints + digest trigger
  backend/app/schemas/alerts.py              Pydantic schemas for alerts + notifications
  backend/app/services/notification_service.py  Create/list/mark-read, alert rule evaluation, email
  backend/app/services/report_service.py     CSV generators (domains + SEO audit)

### Backend — Updated Files
  backend/app/models/models.py               REPLACE — adds AlertRule + Notification tables
  backend/app/tasks/seo_tasks.py             REPLACE — evaluates alert rules after every SEO check
  backend/app/main.py                        REPLACE — registers alerts + reports routers

### Frontend — New Files
  frontend/src/services/alerts.service.ts
  frontend/src/components/ui/NotificationBell.tsx   Bell icon with unread badge + dropdown
  frontend/src/pages/user/AlertsPage.tsx            Alert rules + notifications page
  frontend/src/pages/user/ReportsPage.tsx           Export builder + quick exports + digest

### Frontend — Updated Files
  frontend/src/App.tsx                       REPLACE — adds /alerts and /reports routes
  frontend/src/index.css                     REPLACE — adds notification bell styles
  frontend/src/components/layout/AppLayout.tsx  REPLACE — adds Alerts/Reports nav + bell

---

## HOW TO INSTALL

### Step 1 — Copy all files
Copy backend/ and frontend/ from this patch into your seo-tool/ folder,
replacing files when asked.

### Step 2 — Drop new tables in MySQL
The models.py adds 2 new tables: alert_rules and notifications.
The app will create them automatically on startup (create_all).

BUT first drop seo_automation DB and recreate to avoid conflicts:
  In phpMyAdmin → seo_automation → Operations → Drop the database
  Then: CREATE DATABASE seo_automation CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

OR just let FastAPI auto-create the new tables on next startup.
If you get a "Table already exists" error, use the drop + recreate approach.

### Step 3 — Restart backend
  uvicorn app.main:app --reload

### Step 4 — Restart frontend
  npm run dev

---

## NEW PAGES

  /alerts     — Create/edit/delete alert rules + view notifications
  /reports    — Export builder (CSV), quick exports, email digest

## NOTIFICATION BELL
  A bell icon appears in the sidebar footer next to logout.
  Shows unread count badge, dropdown with recent notifications.
  Clicking an unread notification marks it as read.
  Polls every 30 seconds for new notifications.

---

## NEW API ENDPOINTS

  GET    /api/v1/alerts/rules                    List user's alert rules
  POST   /api/v1/alerts/rules                    Create alert rule
  PUT    /api/v1/alerts/rules/{id}               Update alert rule
  DELETE /api/v1/alerts/rules/{id}               Delete alert rule

  GET    /api/v1/alerts/notifications            List notifications (paginated)
  GET    /api/v1/alerts/notifications/unread-count   Unread count for bell
  POST   /api/v1/alerts/notifications/{id}/read  Mark one as read
  POST   /api/v1/alerts/notifications/read-all   Mark all as read
  POST   /api/v1/alerts/test                     Admin: send test notification

  GET    /api/v1/reports/domains/csv             Export domain list CSV
  GET    /api/v1/reports/seo-audit/csv           Export SEO audit CSV
  POST   /api/v1/reports/digest/send             Admin: send digest email
  GET    /api/v1/reports/summary                 Summary stats for report builder

---

## ALERT CONDITIONS

  score_above   — Alert when a domain scores >= threshold (e.g. 70)
  score_below   — Alert when a domain scores < threshold (e.g. 40)
  score_drop    — Alert when score drops by >= N points (e.g. 20)
  check_failed  — Alert whenever a domain SEO check fails

Alerts fire automatically after every domain SEO check (via Celery).
They also fire when you use the manual SEO Checker page.

---

## EMAIL ALERTS (optional)
Configure SMTP in backend/.env:
  SMTP_HOST=smtp.sendgrid.net
  SMTP_PORT=587
  SMTP_USER=apikey
  SMTP_PASSWORD=your-sendgrid-key
  EMAILS_FROM=noreply@yourdomain.com

Without SMTP configured, in-app notifications still work perfectly.
