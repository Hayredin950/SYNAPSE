#!/usr/bin/env bash
# ============================================================
# SYNAPSE — AWS EC2 Bootstrap / User Data Script
# ============================================================
# Run once on a fresh Ubuntu 22.04 LTS t3.medium/t3.large.
# Installs: Docker, Docker Compose v2, Certbot, AWS CLI v2,
#           CloudWatch agent, fail2ban, and clones the repo.
#
# Usage (EC2 User Data):
#   Paste this script into EC2 Launch Template → User Data
#   (base64-encoded or raw script mode)
#
# Usage (manual):
#   curl -sSL https://raw.githubusercontent.com/HayreKhan750/SYNAPSE/main/scripts/ec2_bootstrap.sh | sudo bash
# ============================================================

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

LOG="/var/log/synapse-bootstrap.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== SYNAPSE EC2 Bootstrap starting at $(date) ==="

# ── 1. System update ──────────────────────────────────────────────────────────
apt-get update -y
apt-get upgrade -y
apt-get install -y \
  curl wget git unzip jq \
  ca-certificates gnupg lsb-release \
  htop iotop nethogs \
  fail2ban ufw \
  python3-pip python3-certbot-nginx \
  awscli

# ── 2. Docker CE ──────────────────────────────────────────────────────────────
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

# Add ubuntu user to docker group
usermod -aG docker ubuntu

# ── 3. AWS CLI v2 ─────────────────────────────────────────────────────────────
curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
unzip -q /tmp/awscliv2.zip -d /tmp
/tmp/aws/install --update
rm -rf /tmp/awscliv2.zip /tmp/aws

# ── 4. CloudWatch Agent ───────────────────────────────────────────────────────
wget -q https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb \
  -O /tmp/cwa.deb
dpkg -i /tmp/cwa.deb
rm /tmp/cwa.deb

# CloudWatch agent config
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CWCONFIG'
{
  "agent": { "metrics_collection_interval": 60, "run_as_user": "root" },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/nginx/access.log",
            "log_group_name": "/synapse/nginx/access",
            "log_stream_name": "{instance_id}",
            "timezone": "UTC"
          },
          {
            "file_path": "/var/log/nginx/error.log",
            "log_group_name": "/synapse/nginx/error",
            "log_stream_name": "{instance_id}",
            "timezone": "UTC"
          },
          {
            "file_path": "/var/log/synapse-bootstrap.log",
            "log_group_name": "/synapse/bootstrap",
            "log_stream_name": "{instance_id}",
            "timezone": "UTC"
          }
        ]
      }
    }
  },
  "metrics": {
    "namespace": "SYNAPSE/EC2",
    "metrics_collected": {
      "cpu":    { "measurement": ["cpu_usage_idle","cpu_usage_user","cpu_usage_system"], "metrics_collection_interval": 60 },
      "disk":   { "measurement": ["used_percent","inodes_free"], "resources": ["/"], "metrics_collection_interval": 60 },
      "mem":    { "measurement": ["mem_used_percent","mem_available"], "metrics_collection_interval": 60 },
      "net":    { "measurement": ["bytes_sent","bytes_recv"], "metrics_collection_interval": 60 },
      "swap":   { "measurement": ["swap_used_percent"], "metrics_collection_interval": 60 }
    }
  }
}
CWCONFIG

systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent

# ── 5. UFW firewall ───────────────────────────────────────────────────────────
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# ── 6. fail2ban ───────────────────────────────────────────────────────────────
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

[nginx-http-auth]
enabled  = true
filter   = nginx-http-auth
port     = http,https
logpath  = /var/log/nginx/error.log
maxretry = 5

[nginx-limit-req]
enabled  = true
filter   = nginx-limit-req
port     = http,https
logpath  = /var/log/nginx/error.log
maxretry = 10
F2B

systemctl enable fail2ban
systemctl start fail2ban

# ── 7. Swap space (2GB — prevents OOM on t3.medium) ──────────────────────────
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl vm.swappiness=10
  echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# ── 8. Docker system tuning ───────────────────────────────────────────────────
cat > /etc/docker/daemon.json <<'DOCKERD'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "100m", "max-file": "5" },
  "default-ulimits": { "nofile": { "soft": 65536, "hard": 65536 } },
  "live-restore": true,
  "storage-driver": "overlay2"
}
DOCKERD
systemctl restart docker

# ── 9. Clone / update repo ────────────────────────────────────────────────────
if [ ! -d /opt/synapse ]; then
  git clone https://github.com/HayreKhan750/SYNAPSE.git /opt/synapse
else
  cd /opt/synapse && git pull --rebase
fi

# Create required directories
mkdir -p /opt/synapse/{media,staticfiles,logs}
chmod 755 /opt/synapse/{media,staticfiles,logs}

# ── 10. SSL via Certbot ───────────────────────────────────────────────────────
# Run manually after DNS is pointing to this instance:
#   certbot --nginx -d synapse.app -d www.synapse.app -d api.synapse.app \
#     --non-interactive --agree-tos -m admin@synapse.app
echo "NOTE: Run certbot manually after DNS propagation:"
echo "  certbot --nginx -d synapse.app -d www.synapse.app --agree-tos -m admin@synapse.app"

# ── 11. Set up Docker Compose service (auto-start on reboot) ─────────────────
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
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable synapse

echo "=== SYNAPSE EC2 Bootstrap COMPLETE at $(date) ==="
echo "Next steps:"
echo "  1. Upload .env.prod to /opt/synapse/.env.prod"
echo "  2. Run: sudo systemctl start synapse"
echo "  3. Run Certbot for SSL"
echo "  4. Verify: docker compose -f docker-compose.prod.yml ps"
