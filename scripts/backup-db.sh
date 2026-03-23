#!/bin/bash
# ─── MySQL Database Backup Script ─────────────────────────────────────────────
# Add to crontab: 0 2 * * * /opt/seo-automation/scripts/backup-db.sh >> /var/log/seo-backup.log 2>&1

set -e

# Config
BACKUP_DIR="/opt/seo-automation/backups"
CONTAINER="seo_mysql"
DB_NAME="seo_automation"
DB_USER="root"
DB_PASSWORD="${DB_ROOT_PASSWORD:-rootpassword}"
RETENTION_DAYS=7
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="seo_automation_${DATE}.sql.gz"

# S3 config (optional — leave empty to skip)
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
AWS_PROFILE="${AWS_PROFILE:-default}"

echo "[$(date)] Starting backup: $FILENAME"

# ─── Create backup directory ──────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"

# ─── Dump database ────────────────────────────────────────────────────────────
docker exec "$CONTAINER" mysqldump \
    -u"$DB_USER" -p"$DB_PASSWORD" \
    --single-transaction \
    --quick \
    --lock-tables=false \
    "$DB_NAME" | gzip > "$BACKUP_DIR/$FILENAME"

SIZE=$(du -sh "$BACKUP_DIR/$FILENAME" | cut -f1)
echo "[$(date)] Backup complete: $FILENAME ($SIZE)"

# ─── Upload to S3 (optional) ──────────────────────────────────────────────────
if [ -n "$S3_BUCKET" ]; then
    aws s3 cp "$BACKUP_DIR/$FILENAME" "s3://$S3_BUCKET/db-backups/$FILENAME" \
        --profile "$AWS_PROFILE"
    echo "[$(date)] Uploaded to S3: s3://$S3_BUCKET/db-backups/$FILENAME"
fi

# ─── Remove old backups ───────────────────────────────────────────────────────
find "$BACKUP_DIR" -name "seo_automation_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Cleaned up backups older than $RETENTION_DAYS days"

echo "[$(date)] Backup done."
