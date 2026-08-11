#!/usr/bin/env bash
# ============================================================
# SYNAPSE — Oracle Cloud ARM (Ampere A1) Bootstrap
# ============================================================
# Provisioning script for an Oracle Cloud Always-Free ARM instance
# (4 vCPU / 24 GB / 200 GB disk). Run ONCE as the ubuntu user:
#
#   bash <(curl -sL https://raw.githubusercontent.com/Hayredin950/SYNAPSE/main/scripts/oracle_bootstrap.sh)
#
# What it does:
#   1. Installs Docker CE + compose plugin (native arm64)
#   2. Hardens the box: UFW (22/80/443), fail2ban, swap
#   3. Clones the repo to /opt/synapse
#   4. Generates /opt/synapse/.env.prod from .env.prod.example
#      (auto-generates SECRET_KEY / DB / Redis / Flower passwords)
#   5. Generates nginx vhost from the template (envsubst)
#   6. Installs a DuckDNS cron that keeps the A record pointed here
#   7. Installs certbot + a renewal hook that copies certs into
#      the nginx certs mount
#   8. Builds all images NATIVELY on arm64 (fast — PyPI ships
#      aarch64 torch wheels) and starts the stack
#   9. Installs a systemd unit so the stack survives reboots
#
# PRE-REQUISITES (done before running):
#   • Oracle Cloud instance created (Ubuntu 22.04/24.04, Ampere A1)
#   • Inbound rules allow TCP 22, 80, 443
#   • A DuckDNS hostname exists, e.g. synapseai.duckdns.org
#   • SSH key added to ~/.ssh/authorized_keys so GitHub Actions can deploy
# ============================================================

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

LOG="/var/log/synapse-bootstrap.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== SYNAPSE Oracle ARM Bootstrap starting at $(date) ==="

# ── Config (edit these BEFORE running) ────────────────────────────────────────
DUCKDNS_DOMAIN="${DUCKDNS_DOMAIN:-synapseai}"            # DuckDNS hostname (no .duckdns.org)
DUCKDNS_TOKEN="${DUCKDNS_TOKEN:-CHANGE_ME}"            # DuckDNS token
APP_URL="${APP_URL:-https://synapse-one-blond.vercel.app}" # Vercel frontend URL
GITHUB_REPO="${GITHUB_REPO:-https://github.com/Hayredin950/SYNAPSE.git}"
EMAIL_FOR_TLS="${EMAIL_FOR_TLS:-admin@synapse.ai}"

PUBLIC_IP="$(curl -4 -s https://ifconfig.me || echo '')"
echo "Public IP detected: ${PUBLIC_IP:-UNKNOWN}"
echo "DuckDNS domain: ${DUCKDNS_DOMAIN}.duckdns.org"
echo "Vercel app URL: ${APP_URL}"
echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
apt-get update -y
apt-get install -y \
  curl wget git unzip jq htop \
  ca-certificates gnupg lsb-release \
  ufw fail2ban \
  python3-pip python3-certbot-nginx \
  gettext-base

# ── 2. Docker CE (native arm64) ───────────────────────────────────────────────
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker
usermod -aG docker ubuntu

# Docker logging + live-restore tuning
cat > /etc/docker/daemon.json <<'DOCKERD'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "100m", "max-file": "5" },
  "live-restore": true,
  "storage-driver": "overlay2"
}
DOCKERD
systemctl restart docker

# ── 3. Swap (small safety net on 24 GB box) ───────────────────────────────────
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl vm.swappiness=10
  echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# ── 4. UFW firewall ───────────────────────────────────────────────────────────
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ── 5. fail2ban ───────────────────────────────────────────────────────────────
cat > /etc/fail2ban/jail.local <<'F2B'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port    = ssh
filter  = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime  = 86400
F2B
systemctl enable fail2ban
systemctl start fail2ban

# ── 6. Clone / update the repo ────────────────────────────────────────────────
if [ ! -d /opt/synapse/.git ]; then
  git clone "$GITHUB_REPO" /opt/synapse
else
  cd /opt/synapse && git pull --rebase
fi
cd /opt/synapse
mkdir -p infrastructure/nginx/certs

# ── 7. .env.prod — generate from example if absent ────────────────────────────
if [ ! -f /opt/synapse/.env.prod ]; then
  echo "=== Generating .env.prod with random secrets ==="
  SECRET="$(python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' 2>/dev/null || openssl rand -hex 32)"
  JWT_KEY="$(openssl rand -hex 32)"
  DB_PASS="$(openssl rand -hex 24)"
  REDIS_PASS="$(openssl rand -hex 24)"
  FLOWER_PASS="$(openssl rand -hex 16)"

  cp /opt/synapse/.env.prod.example /opt/synapse/.env.prod
  # Ensure required keys exist even if the example drifted
  for K in SECRET_KEY DB_PASSWORD REDIS_PASSWORD FLOWER_PASSWORD JWT_SIGNING_KEY \
           EMAIL_HOST_PASSWORD EMAIL_HOST_USER DEFAULT_FROM_EMAIL ALLOWED_HOSTS \
           CSRF_TRUSTED_ORIGINS CORS_ALLOWED_ORIGINS FRONTEND_URL \
           GROQ_API_KEY NVIDIA_API_KEY GEMINI_API_KEY DATABASE_URL REDIS_URL; do
    grep -q "^${K}=" /opt/synapse/.env.prod || echo "${K}=" >> /opt/synapse/.env.prod
  done

  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|"                    /opt/synapse/.env.prod
  sed -i "s|^JWT_SIGNING_KEY=.*|JWT_SIGNING_KEY=${JWT_KEY}|"          /opt/synapse/.env.prod
  sed -i "s|^DB_PASSWORD=.*|DB_PASSWORD=${DB_PASS}|"                  /opt/synapse/.env.prod
  sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${REDIS_PASS}|"         /opt/synapse/.env.prod
  sed -i "s|^FLOWER_PASSWORD=.*|FLOWER_PASSWORD=${FLOWER_PASS}|"      /opt/synapse/.env.prod
  sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=${DUCKDNS_DOMAIN}.duckdns.org,localhost,127.0.0.1|" /opt/synapse/.env.prod
  sed -i "s|^CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=https://${DUCKDNS_DOMAIN}.duckdns.org,${APP_URL}|" /opt/synapse/.env.prod
  sed -i "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=${APP_URL}|" /opt/synapse/.env.prod
  sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=${APP_URL}|"                /opt/synapse/.env.prod
  sed -i "s|^DEFAULT_FROM_EMAIL=.*|DEFAULT_FROM_EMAIL=SYNAPSE <noreply@synapse.ai>|" /opt/synapse/.env.prod

  # The box runs its OWN Postgres + Redis in Docker — never use the cloud
  # (Neon/Upstash) URLs carried over from a laptop .env.prod. production.py
  # falls back to the local DB_*/REDIS_* vars when these are empty.
  sed -i "s|^DATABASE_URL=.*|DATABASE_URL=|" /opt/synapse/.env.prod
  sed -i "s|^REDIS_URL=.*|REDIS_URL=|"         /opt/synapse/.env.prod

  echo "  → /opt/synapse/.env.prod created. EDIT IT to add:"
  echo "    • EMAIL_HOST_USER / EMAIL_HOST_PASSWORD (Brevo SMTP)"
  echo "    • GROQ_API_KEY / NVIDIA_API_KEY / GEMINI_API_KEY"
else
  echo "=== .env.prod already exists — leaving it untouched ==="
fi
chmod 600 /opt/synapse/.env.prod

# ── 8. nginx vhost — generate from template ───────────────────────────────────
export DOMAIN="${DUCKDNS_DOMAIN}.duckdns.org"
export APP_URL
envsubst '$DOMAIN $APP_URL' \
  < /opt/synapse/infrastructure/nginx/conf.d/synapse.conf.template \
  > /opt/synapse/infrastructure/nginx/conf.d/synapse.conf

# Basic auth for Flower (generated with openssl — no apache2-utils needed)
_FLOWER_USER="${FLOWER_USER:-admin}"
_FLOWER_PASS="${FLOWER_PASSWORD:-$(grep '^FLOWER_PASSWORD=' /opt/synapse/.env.prod | cut -d= -f2)}"
echo "${_FLOWER_USER}:$(openssl passwd -apr1 "${_FLOWER_PASS}")" \
  > /opt/synapse/infrastructure/nginx/.htpasswd
chmod 600 /opt/synapse/infrastructure/nginx/.htpasswd

# ── 9. DuckDNS cron — keep A record pointed at this box ───────────────────────
if [ "$DUCKDNS_TOKEN" != "CHANGE_ME" ]; then
  cat > /usr/local/bin/duckdns-update.sh <<'DDNS'
#!/usr/bin/env bash
DOMAIN="REPLACE_DOMAIN"
TOKEN="REPLACE_TOKEN"
IP="$(curl -4 -s https://ifconfig.me)"
curl -s "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=${IP}" > /dev/null
DDNS
  sed -i "s/REPLACE_DOMAIN/${DUCKDNS_DOMAIN}/; s/REPLACE_TOKEN/${DUCKDNS_TOKEN}/" /usr/local/bin/duckdns-update.sh
  chmod +x /usr/local/bin/duckdns-update.sh
  echo "*/5 * * * * ubuntu /usr/local/bin/duckdns-update.sh" > /etc/cron.d/duckdns
  chmod 644 /etc/cron.d/duckdns
  /usr/local/bin/duckdns-update.sh && echo "  → DuckDNS updated to ${PUBLIC_IP}"
else
  echo "  ⚠ DUCKDNS_TOKEN not set — skipping DuckDNS cron. Run /usr/local/bin/duckdns-update.sh manually after editing it."
fi

# ── 10. Let's Encrypt (certbot) ────────────────────────────────────────────────
# nginx must be listening on :80 for the HTTP-01 challenge.
# We issue the cert BEFORE the full stack is up, using a throwaway listener.
if [ ! -f /etc/letsencrypt/live/${DUCKDNS_DOMAIN}.duckdns.org/fullchain.pem ]; then
  apt-get install -y nginx-light >/dev/null 2>&1 || true
  systemctl stop nginx 2>/dev/null || true
  cat > /etc/nginx/sites-available/synapse-challenge <<'NGX'
server {
  listen 80;
  server_name _;
  location /.well-known/acme-challenge/ { root /var/www/certbot; }
  location / { return 404; }
}
NGX
  ln -sf /etc/nginx/sites-available/synapse-challenge /etc/nginx/sites-enabled/synapse-challenge
  rm -f /etc/nginx/sites-enabled/default
  mkdir -p /var/www/certbot
  systemctl restart nginx

  certbot certonly --webroot -w /var/www/certbot \
    -d "${DUCKDNS_DOMAIN}.duckdns.org" \
    --non-interactive --agree-tos -m "${EMAIL_FOR_TLS}" || {
      echo "  ⚠ certbot failed — check that DNS (${DUCKDNS_DOMAIN}.duckdns.org) resolves to ${PUBLIC_IP} and port 80 is open."
      echo "    Re-run: certbot certonly --webroot -w /var/www/certbot -d ${DUCKDNS_DOMAIN}.duckdns.org"
      echo "    Fix DNS, then re-run this whole script — it is idempotent."
    }
  systemctl stop nginx 2>/dev/null || true
  systemctl disable nginx 2>/dev/null || true
fi

# Fail fast if TLS cannot be provisioned — nginx refuses to start without certs
if [ ! -f "/etc/letsencrypt/live/${DUCKDNS_DOMAIN}.duckdns.org/fullchain.pem" ]; then
  echo "  ✖ TLS certs missing. nginx will not start without them."
  echo "    Point ${DUCKDNS_DOMAIN}.duckdns.org → ${PUBLIC_IP} (A record / DuckDNS cron), open port 80, then re-run this script."
  exit 1
fi

# Copy certs into the nginx mount + renewal hook so they stay fresh
if [ -f /etc/letsencrypt/live/${DUCKDNS_DOMAIN}.duckdns.org/fullchain.pem ]; then
  cp -L /etc/letsencrypt/live/${DUCKDNS_DOMAIN}.duckdns.org/{fullchain.pem,privkey.pem} /opt/synapse/infrastructure/nginx/certs/
  cat > /etc/letsencrypt/renewal-hooks/deploy/synapse-copy.sh <<'HOOK'
#!/usr/bin/env bash
set -euo pipefail
D=/etc/letsencrypt/live/REPLACE_DOMAIN.duckdns.org
cp -L "$D/fullchain.pem" /opt/synapse/infrastructure/nginx/certs/fullchain.pem
cp -L "$D/privkey.pem"   /opt/synapse/infrastructure/nginx/certs/privkey.pem
docker compose -f /opt/synapse/docker-compose.prod.yml restart nginx 2>/dev/null || true
HOOK
  sed -i "s/REPLACE_DOMAIN/${DUCKDNS_DOMAIN}/" /etc/letsencrypt/renewal-hooks/deploy/synapse-copy.sh
  chmod +x /etc/letsencrypt/renewal-hooks/deploy/synapse-copy.sh
  echo "  → TLS certs installed + renewal hook configured"
fi

# ── 11. systemd unit — auto-start on reboot ───────────────────────────────────
cat > /etc/systemd/system/synapse.service <<'SERVICE'
[Unit]
Description=SYNAPSE Application Stack
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/synapse
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d --remove-orphans
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
SERVICE
systemctl daemon-reload
systemctl enable synapse

# ── 12. Build images natively (arm64) + start the stack ───────────────────────
cd /opt/synapse
echo "=== Building images natively on arm64 (torch aarch64 wheels from PyPI) ==="
# Only 'backend' and 'fastapi_ai' have build sections; celery_worker,
# celery_beat and flower reuse the backend image, so building it once is enough.
mkdir -p infrastructure/nginx/certbot-webroot
docker compose -f docker-compose.prod.yml build \
  backend fastapi_ai || {
    echo "  ⚠ Build failed — inspect with: docker compose -f docker-compose.prod.yml build backend"
    exit 1
  }

echo "=== Starting stack ==="
docker compose -f docker-compose.prod.yml up -d --remove-orphans

# ── 13. Verify ────────────────────────────────────────────────────────────────
sleep 20
echo ""
echo "=== Container status ==="
docker compose -f docker-compose.prod.yml ps
echo ""
echo "=== Health check ==="
curl -sf "https://${DUCKDNS_DOMAIN}.duckdns.org/api/v1/health/" && echo " ✓ API is LIVE at https://${DUCKDNS_DOMAIN}.duckdns.org" || echo "  ⚠ Health check not ready yet — give it 30–60s, then: curl https://${DUCKDNS_DOMAIN}.duckdns.org/api/v1/health/"

echo ""
echo "============================================================"
echo " SYNAPSE BOOTSTRAP COMPLETE"
echo "============================================================"
echo "  API:      https://${DUCKDNS_DOMAIN}.duckdns.org"
echo "  Frontend: ${APP_URL}  (deploy: cd frontend && npx vercel --prod)"
echo "  Admin:    https://${DUCKDNS_DOMAIN}.duckdns.org/admin  (create superuser: docker compose exec backend python manage.py createsuperuser)"
echo ""
echo "  NEXT STEPS:"
echo "   1. Edit /opt/synapse/.env.prod — set Brevo SMTP + AI keys"
echo "   2. docker compose -f docker-compose.prod.yml restart backend celery_worker celery_beat"
echo "   3. Add the GitHub Actions SSH deploy key:"
echo "        ssh-keyscan ${PUBLIC_IP} >> ~/.ssh/known_hosts"
echo "        # public key: $(cat ~/.ssh/id_ed25519.pub 2>/dev/null || echo 'generate one with ssh-keygen')"
echo "   4. cd /opt/synapse && docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser"
echo "   5. Deploy the frontend to Vercel with NEXT_PUBLIC_API_URL=https://${DUCKDNS_DOMAIN}.duckdns.org"
echo "============================================================"
