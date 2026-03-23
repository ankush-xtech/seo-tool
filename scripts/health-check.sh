#!/bin/bash
# ─── Service Health Check Script ──────────────────────────────────────────────
# Usage: bash scripts/health-check.sh
# Add to crontab for monitoring: */5 * * * * bash /opt/seo-automation/scripts/health-check.sh

API_URL="${API_URL:-http://localhost:8000}"
ALERT_EMAIL="${ALERT_EMAIL:-}"

check_service() {
    local name=$1
    local url=$2
    local expected=$3

    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null)

    if [ "$response" = "$expected" ]; then
        echo "[OK]   $name ($response)"
        return 0
    else
        echo "[FAIL] $name — expected $expected, got $response"
        return 1
    fi
}

check_container() {
    local name=$1
    local container=$2
    local status=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "not found")

    if [ "$status" = "running" ]; then
        echo "[OK]   $name (running)"
        return 0
    else
        echo "[FAIL] $name — status: $status"
        return 1
    fi
}

echo "=== Health Check $(date) ==="

FAILED=0

# API
check_service "FastAPI"     "$API_URL/api/health"  "200" || FAILED=$((FAILED+1))
check_service "Nginx HTTP"  "http://localhost/nginx-health" "200" || FAILED=$((FAILED+1))

# Containers
check_container "MySQL"    "seo_mysql"    || FAILED=$((FAILED+1))
check_container "Redis"    "seo_redis"    || FAILED=$((FAILED+1))
check_container "API"      "seo_api"      || FAILED=$((FAILED+1))
check_container "Worker"   "seo_worker"   || FAILED=$((FAILED+1))
check_container "Beat"     "seo_beat"     || FAILED=$((FAILED+1))
check_container "Frontend" "seo_frontend" || FAILED=$((FAILED+1))
check_container "Nginx"    "seo_nginx"    || FAILED=$((FAILED+1))

# Disk space warning
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USAGE" -gt 85 ]; then
    echo "[WARN] Disk usage is ${DISK_USAGE}% — consider cleanup"
    FAILED=$((FAILED+1))
else
    echo "[OK]   Disk usage: ${DISK_USAGE}%"
fi

echo ""
if [ $FAILED -eq 0 ]; then
    echo "All checks passed."
else
    echo "$FAILED check(s) FAILED."
    # Send alert email if configured
    if [ -n "$ALERT_EMAIL" ]; then
        echo "SEO Automation Tool health check failed ($FAILED failures) at $(date)" | \
            mail -s "Health Check Failed" "$ALERT_EMAIL"
    fi
    exit 1
fi
