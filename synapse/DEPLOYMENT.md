# SYNAPSE — Production Deployment Runbook

> **Last updated:** Phase 8.2 | **Owner:** Platform Team

---

## Table of Contents
1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [First-Time Setup](#first-time-setup)
4. [Deploying a New Version](#deploying-a-new-version)
5. [Rollback Procedure](#rollback-procedure)
6. [GitHub Actions Secrets](#github-actions-secrets)
7. [Monitoring & Alerts](#monitoring--alerts)
8. [Troubleshooting Runbooks](#troubleshooting-runbooks)
9. [Database Migrations](#database-migrations)
10. [SSL Certificate Renewal](#ssl-certificate-renewal)

---

## Architecture

```
Internet
    │
    ▼
┌─────────────────────┐
│  AWS ALB (optional) │  ← HTTPS termination / health routing
└─────────────────────┘
    │
    ▼
┌─────────────────────┐
│  EC2 t3.medium      │  ← Ubuntu 22.04 LTS
│  ┌───────────────┐  │
│  │ Nginx 1.27    │  │  ← Reverse proxy / static files / rate limiting
│  └───────────────┘  │
│  ┌───────────────┐  │
│  │ Django        │  │  ← Gunicorn 4 workers + gthread
│  │ FastAPI AI    │  │  ← Uvicorn 2 workers + uvloop
│  │ Next.js       │  │  ← Node.js standalone output
│  │ Celery Worker │  │  ← 4 concurrent tasks
│  │ Celery Beat   │  │  ← Scheduled tasks
│  └───────────────┘  │
└─────────────────────┘
    │              │
    ▼              ▼
AWS RDS        AWS ElastiCache
PostgreSQL 15  Redis 7
(pgvector)
    │
    ▼
AWS S3 (media / documents)
```

---

## Prerequisites

### Required GitHub Secrets

Go to: **GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

| Secret | Description | Example |
|--------|-------------|---------|
| `EC2_HOST` | EC2 public IP or hostname | `54.123.45.67` |
| `EC2_USER` | SSH username | `ubuntu` |
| `EC2_SSH_KEY` | Private SSH key (full content of `.pem`) | `-----BEGIN RSA PRIVATE KEY-----...` |
| `PRODUCTION_URL` | Full production URL | `https://synapse.app` |
| `NEXT_PUBLIC_API_URL` | API URL for frontend build | `https://api.synapse.app` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook (optional) | `https://hooks.slack.com/...` |
| `CODECOV_TOKEN` | Codecov upload token (optional) | `abc123...` |

> **Note:** `GITHUB_TOKEN` is automatically provided — no setup needed.

---

## First-Time Setup

### 1. Launch EC2 Instance

```bash
# Recommended: Ubuntu 22.04 LTS, t3.medium (backend) or t3.large (with AI engine)
# Attach IAM role with: AmazonS3FullAccess, CloudWatchAgentServerPolicy

# Run bootstrap script on the instance:
curl -sSL https://raw.githubusercontent.com/HayreKhan750/SYNAPSE/main/scripts/ec2_bootstrap.sh | sudo bash
```

### 2. Configure AWS RDS PostgreSQL

```sql
-- Run on RDS after creation:
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
```

```bash
# RDS recommended settings:
# - Engine: PostgreSQL 15.x
# - Instance: db.t3.medium (dev) / db.r6g.large (prod)
# - Storage: 100GB gp3, auto-scaling enabled
# - Multi-AZ: enabled in production
# - Parameter group: default.postgres15 (modify shared_preload_libraries=pg_stat_statements)
# - Backup retention: 7 days
# - Enable Enhanced Monitoring (60s granularity)
```

### 3. Configure AWS ElastiCache Redis

```bash
# ElastiCache Redis settings:
# - Engine: Redis 7.x
# - Node type: cache.t3.small (dev) / cache.r6g.large (prod)
# - Cluster mode: disabled (single primary for simplicity)
# - Multi-AZ: enabled in production
# - Encryption at rest: enabled
# - Encryption in transit (TLS): enabled
# - Auth token: set strong random password
```

### 4. Create S3 Bucket

```bash
# Create bucket
aws s3 mb s3://synapse-media-prod --region us-east-1

# Block public access (all 4 options)
aws s3api put-public-access-block \
  --bucket synapse-media-prod \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket synapse-media-prod \
  --versioning-configuration Status=Enabled

# Enable server-side encryption
aws s3api put-bucket-encryption \
  --bucket synapse-media-prod \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Lifecycle rule: delete incomplete multipart uploads after 7 days
aws s3api put-bucket-lifecycle-configuration \
  --bucket synapse-media-prod \
  --lifecycle-configuration '{
    "Rules": [{
      "ID": "abort-incomplete-multipart",
      "Status": "Enabled",
      "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 7}
    }]
  }'
```

### 5. Upload Production Environment File

```bash
# On your local machine:
scp .env.prod ubuntu@<EC2_HOST>:/opt/synapse/.env.prod
chmod 600 /opt/synapse/.env.prod
```

### 6. Start the Application Stack

```bash
# SSH into EC2
ssh -i synapse-key.pem ubuntu@<EC2_HOST>

cd /opt/synapse

# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u HayreKhan750 --password-stdin

# Pull and start
IMAGE_TAG=latest docker compose -f docker-compose.prod.yml up -d

# Check all services are healthy
docker compose -f docker-compose.prod.yml ps
```

### 7. SSL Certificate (Let's Encrypt)

```bash
# Make sure DNS is pointing to EC2 IP before running:
sudo certbot --nginx \
  -d synapse.app \
  -d www.synapse.app \
  --non-interactive \
  --agree-tos \
  -m admin@synapse.app

# Test auto-renewal:
sudo certbot renew --dry-run

# Certbot auto-renewal cron is set up automatically.
# Verify: sudo systemctl status certbot.timer
```

### 8. Start Monitoring Stack

```bash
cd /opt/synapse

# Copy monitoring env vars to .env.prod (add GRAFANA_PASSWORD, GRAFANA_SECRET_KEY)
docker compose -f docker-compose.prod.yml \
               -f docker-compose.monitoring.yml up -d

# Access Grafana at: https://synapse.app/grafana/
# Default login: admin / (GRAFANA_PASSWORD from .env.prod)
```

---

## Deploying a New Version

### Automatic (Recommended)
Push to `main` branch → GitHub Actions CD pipeline runs automatically:
1. Builds multi-arch Docker images
2. Pushes to GHCR with SHA + latest tags
3. SSH deploys to EC2
4. Runs migrations + collectstatic
5. Rolling restart (zero downtime)
6. Health check verification

### Manual Deploy

```bash
ssh -i synapse-key.pem ubuntu@<EC2_HOST>
cd /opt/synapse

# Pull latest code
git pull --rebase origin main

# Set image tag (use git SHA for reproducibility)
export IMAGE_TAG=$(git rev-parse --short HEAD)
export GITHUB_REPOSITORY=hayrekhan750/synapse

# Pull new images
docker compose -f docker-compose.prod.yml pull

# Run migrations (zero-downtime: must be backward-compatible)
docker compose -f docker-compose.prod.yml run --rm backend \
  python manage.py migrate --noinput

# Collect static files
docker compose -f docker-compose.prod.yml run --rm backend \
  python manage.py collectstatic --noinput

# Rolling restart
docker compose -f docker-compose.prod.yml up -d \
  --remove-orphans \
  backend fastapi_ai frontend celery_worker celery_beat

# Verify
docker compose -f docker-compose.prod.yml ps
curl -sf https://synapse.app/api/v1/health/ && echo "✅ Health OK"
```

---

## Rollback Procedure

```bash
ssh -i synapse-key.pem ubuntu@<EC2_HOST>
cd /opt/synapse

# Find previous working SHA from git log or GitHub Actions
PREVIOUS_SHA=abc1234

export IMAGE_TAG=$PREVIOUS_SHA
export GITHUB_REPOSITORY=hayrekhan750/synapse

# Pull previous images
docker compose -f docker-compose.prod.yml pull

# Restart with previous images
docker compose -f docker-compose.prod.yml up -d \
  --remove-orphans \
  backend fastapi_ai frontend celery_worker celery_beat

# Verify health
curl -sf https://synapse.app/api/v1/health/
docker compose -f docker-compose.prod.yml ps

echo "⏪ Rollback to $PREVIOUS_SHA complete"
```

> **Important:** If the rollback involves database schema changes, restore from RDS snapshot instead of reverting migrations.

---

## Monitoring & Alerts

### Access Points (after setup)

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | `https://synapse.app/grafana/` | `GRAFANA_USER` / `GRAFANA_PASSWORD` |
| Prometheus | `http://EC2_HOST:9090` (internal) | None |
| Alertmanager | `http://EC2_HOST:9093` (internal) | None |
| Flower | `https://synapse.app/flower/` | `FLOWER_USER` / `FLOWER_PASSWORD` |

### Key Dashboards
- **SYNAPSE Overview** — requests/sec, error rate, P95 latency, CPU/memory
- **Celery Tasks** — queue depth, success/failure rates
- **PostgreSQL** — connections, query latency, cache hit ratio
- **Redis** — memory usage, hit rate, commands/sec
- **Nginx** — requests/sec, upstream response time

---

## Troubleshooting Runbooks

### Runbook: High Error Rate

```bash
# 1. Check which endpoints are failing
docker compose -f docker-compose.prod.yml logs --tail=100 backend | grep ERROR

# 2. Check if DB is reachable
docker compose -f docker-compose.prod.yml exec backend \
  python manage.py dbshell -- -c "SELECT 1;"

# 3. Check Celery workers
docker compose -f docker-compose.prod.yml exec celery_worker \
  celery -A config inspect ping

# 4. Check Sentry for exception details
# → https://sentry.io/organizations/synapse/issues/
```

### Runbook: High Memory / OOM

```bash
# Identify memory hog
docker stats --no-stream

# Restart specific service (zero-downtime for stateless services)
docker compose -f docker-compose.prod.yml restart fastapi_ai

# If persistent, scale down Celery concurrency
# Edit .env.prod: CELERY_CONCURRENCY=2
docker compose -f docker-compose.prod.yml up -d celery_worker
```

### Runbook: Database Connection Pool Exhausted

```bash
# Check active connections
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U synapse_user -d synapse_db \
  -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Kill idle connections older than 10 minutes
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U synapse_user -d synapse_db \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
      WHERE state='idle' AND query_start < now() - interval '10 minutes';"
```

---

## Backup & Restore

### Automated Backups (TASK-502)

Daily `pg_dump` backups run at **02:00 UTC** via Celery beat, compressed with gzip, uploaded to S3 with **30-day retention**.

**Required env vars:**
```bash
BACKUP_S3_BUCKET=synapse-backups              # S3 bucket name
AWS_ACCESS_KEY_ID=...                         # AWS credentials
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1                  # optional, default us-east-1
BACKUP_ADMIN_EMAIL=admin@yourcompany.com      # failure alert recipient
BACKUP_SLACK_WEBHOOK=https://hooks.slack.com/services/...  # optional Slack alert
```

**Add to `.env.example`:**
```
BACKUP_S3_BUCKET=
BACKUP_ADMIN_EMAIL=
BACKUP_SLACK_WEBHOOK=
```

**Trigger a manual backup:**
```bash
celery -A config call apps.core.tasks.backup_database
```

**List available backups:**
```bash
aws s3 ls s3://synapse-backups/postgres/ --recursive
```

### Restore Procedure

1. **Download the backup:**
   ```bash
   aws s3 cp s3://synapse-backups/postgres/YYYY/MM/DD.sql.gz /tmp/backup.sql.gz
   ```

2. **Decompress:**
   ```bash
   gunzip /tmp/backup.sql.gz
   # → creates /tmp/backup.sql
   ```

3. **Drop and recreate the database** ⚠️ *This is destructive — ensure you have a confirmed good backup first*:
   ```bash
   psql $DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
   ```

4. **Restore:**
   ```bash
   psql $DATABASE_URL < /tmp/backup.sql
   ```

5. **Run migrations to ensure schema is current:**
   ```bash
   python manage.py migrate --run-syncdb
   ```

6. **Verify:**
   ```bash
   python manage.py check
   python manage.py shell -c "from apps.users.models import User; print(User.objects.count(), 'users')"
   ```

---

## Database Migrations

```bash
# ✅ Safe: additive migrations (new tables, new nullable columns)
# ⚠️  Risky: removing columns/tables (run in 2 deploys: deprecate first)
# ❌ Never: renaming columns in one migration (breaks running instances)

# Run migration dry-run first:
docker compose -f docker-compose.prod.yml run --rm backend \
  python manage.py migrate --noinput --plan

# Run actual migration:
docker compose -f docker-compose.prod.yml run --rm backend \
  python manage.py migrate --noinput

# Check migration state:
docker compose -f docker-compose.prod.yml run --rm backend \
  python manage.py showmigrations
```

---

## SSL Certificate Renewal

```bash
# Certbot auto-renews via systemd timer (every 12 hours, renews if <30 days left)
sudo systemctl status certbot.timer

# Force renewal test:
sudo certbot renew --dry-run

# Force renewal (if auto fails):
sudo certbot renew --force-renewal

# Reload Nginx after renewal:
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```
