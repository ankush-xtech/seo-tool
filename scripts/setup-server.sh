#!/bin/bash
# ─── SEO Automation Tool — Server Setup Script ────────────────────────────────
# Run once on a fresh Ubuntu 22.04 VPS
# Usage: sudo bash setup-server.sh yourdomain.com your@email.com

set -e

DOMAIN=$1
EMAIL=$2

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: sudo bash setup-server.sh yourdomain.com your@email.com"
    exit 1
fi

echo "=== Setting up server for $DOMAIN ==="

# ─── System Update ────────────────────────────────────────────────────────────
apt-get update && apt-get upgrade -y

# ─── Install Docker ───────────────────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker $SUDO_USER
    systemctl enable docker
    systemctl start docker
fi

# ─── Install Docker Compose ───────────────────────────────────────────────────
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# ─── Install Git ──────────────────────────────────────────────────────────────
apt-get install -y git curl ufw fail2ban

# ─── Firewall ─────────────────────────────────────────────────────────────────
echo "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ─── Fail2Ban (brute force protection) ───────────────────────────────────────
systemctl enable fail2ban
systemctl start fail2ban

# ─── Project directory ────────────────────────────────────────────────────────
mkdir -p /opt/seo-automation
cd /opt/seo-automation

echo ""
echo "=== Server setup complete! ==="
echo ""
echo "Next steps:"
echo "1. Clone your repo:  git clone <your-repo-url> /opt/seo-automation"
echo "2. Copy env files:   cp .env.production.example .env.production"
echo "3. Edit all passwords in .env.production and backend/.env.production"
echo "4. Get SSL cert:     bash scripts/init-ssl.sh $DOMAIN $EMAIL"
echo "5. Start app:        docker-compose -f docker-compose.prod.yml up -d"
echo "6. Run migrations:   docker-compose -f docker-compose.prod.yml exec api alembic upgrade head"
