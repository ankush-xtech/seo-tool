#!/bin/bash
# ─── Let's Encrypt SSL Certificate Setup ──────────────────────────────────────
# Run ONCE after server setup to get your first SSL certificate
# Usage: bash scripts/init-ssl.sh yourdomain.com your@email.com

set -e

DOMAIN=$1
EMAIL=$2

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: bash scripts/init-ssl.sh yourdomain.com your@email.com"
    exit 1
fi

echo "=== Getting SSL certificate for $DOMAIN ==="

# ─── Step 1: Start Nginx with HTTP only for ACME challenge ────────────────────
# Temporarily use HTTP-only config
cat > /tmp/nginx-init.conf << EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 200 "SSL setup in progress...";
    }
}
EOF

docker run -d --name nginx_temp \
    -p 80:80 \
    -v /tmp/nginx-init.conf:/etc/nginx/conf.d/default.conf:ro \
    -v certbot_www:/var/www/certbot \
    nginx:1.25-alpine

sleep 3

# ─── Step 2: Get certificate ──────────────────────────────────────────────────
docker run --rm \
    -v certbot_conf:/etc/letsencrypt \
    -v certbot_www:/var/www/certbot \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email $EMAIL \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN \
    -d www.$DOMAIN

# ─── Step 3: Clean up temp nginx ──────────────────────────────────────────────
docker stop nginx_temp && docker rm nginx_temp

echo ""
echo "=== SSL certificate obtained successfully! ==="
echo ""
echo "Certificate location: /etc/letsencrypt/live/$DOMAIN/"
echo ""
echo "Next: Update nginx/conf.d/app.conf with your domain: $DOMAIN"
echo "Then: docker-compose -f docker-compose.prod.yml up -d"
