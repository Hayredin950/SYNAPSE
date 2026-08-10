# SYNAPSE — Full Step-by-Step Deployment Runbook

**Target architecture:** Oracle Cloud ARM (API/AI/db/redis) + Vercel (frontend) + Brevo (email) + DuckDNS/Let's Encrypt (DNS/TLS). All free tiers.

**Your credentials on file:** Brevo SMTP login `sadim9812@gmail.com`, Brevo SMTP key (stored in gitignored `.env.prod`).

---

## PART 1 — Create the Oracle Cloud ARM box (≈20 min)

### 1.1 Sign in / sign up
1. Open **https://cloud.oracle.com** in your browser.
2. Sign in. If you don't have an account: **Sign Up** → fill details → **Verify email** → **Verify phone** → pick **Home region** → Cloud account name = e.g. `synapse`.
3. Wait until you land on the **Console** (10–15 min after signup; you'll get an "account ready" email).

### 1.2 Open Compute
4. In the Console, open the **☰ hamburger menu** (top-left).
5. Click **Compute → Instances**.
6. Click the blue **Create instance** button.

### 1.3 Instance settings (exact values)
| Field | Value |
|---|---|
| Name | `synapse-prod` |
| Placement | leave default (Always Free eligible availability domain) |
| Image | **Canonical Ubuntu 24.04** (or 22.04) — ARM build |
| Shape | click **Change shape** → check **"Specialty and legacy"** → select **Ampere → VM.Standard.A1.Flex** |
| OCPU count | **4** |
| Memory (GB) | **24** |
| Boot volume | **200 GB** (set under Boot volume; 47 GB is the free default — change it) |
| Networking → Assign public IPv4 | **Assign a public IPv4 address** |
| SSH keys | **Paste public keys** → paste the contents of `~/.ssh/id_ed25519.pub` from your laptop |

7. Click **Create**.
8. Wait for the instance state to show **RUNNING** (1–2 min).
9. Copy the **Public IP address** from the instance page. Save it — you'll need it several times below.

### 1.4 Open firewall ports (Network Security List)
> This is the step everyone forgets. Without it, ports 80/443 stay closed and TLS can't be issued.

10. While still on the instance page, scroll to **Resources → Attached VNICs** → click the VNIC.
11. Click **Security Lists** (under Resources on the left).
12. Click the **Default Security List** → **Add Ingress Rules** (or Edit):
    - Add **3 rules**, all `Source CIDR` = `0.0.0.0/0`:
      | IP Protocol | Source Port | Destination Port |
      |---|---|---|
      | TCP | All | **22** |
      | TCP | All | **80** |
      | TCP | All | **443** |
    - (Leave ICMP as-is; SSH rule usually already exists.)
13. Click **Add Ingress Rules** to save.

### 1.5 Test SSH from your laptop
14. On your laptop terminal:
```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<YOUR_PUBLIC_IP>
```
15. You should see the Ubuntu MOTD and a `ubuntu@synapse-prod:~$` prompt. Type `exit` to disconnect.

✅ **Part 1 done when:** SSH works with your key.

---

## PART 2 — DuckDNS (≈5 min)

1. Open **https://www.duckdns.org**.
2. **Sign in** with GitHub / Google / Twitter / Reddit (any).
3. Scroll to **domains** → in the **sub-domain** box type:
   ```
   synapse
   ```
4. Click **add domain**.
5. Your domain now reads: **synapse.duckdns.org** and the page shows your **token** (a long hex string). **Copy the token** and keep it.
6. (Optional but smart) In the same page, set the current IP: the "ip" field → paste your Oracle box's public IP → click **update ip**. This makes the A record point at the box immediately.
7. Confirm in a terminal:
   ```bash
   dig +short synapse.duckdns.org
   ```
   → should print your Oracle public IP.

✅ **Part 2 done when:** `dig` shows your box's IP.

---

## PART 3 — Vercel frontend (≈15 min)

1. Open **https://vercel.com** → **Sign up** → **Continue with GitHub** (authorize; your SYNAPSE repo will appear).
2. Click **Add New… → Project**.
3. Find the **SYNAPSE** repo → **Import**.
4. **Root Directory** → click **Edit** → select **`frontend`** (the Next.js app lives there, not the repo root).
5. **Build & Deployment Settings** — leave defaults (Framework preset auto-detects Next.js).
6. **Environment Variables** — add these (click "Add" each time):
   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://synapse.duckdns.org` |
   | `NEXT_PUBLIC_WS_URL` | `wss://synapse.duckdns.org/ws` |
   | `NEXT_PUBLIC_APP_URL` | `https://<your-project>.vercel.app` |
   | `NEXT_PUBLIC_APP_NAME` | `SYNAPSE` |
7. Click **Deploy**.
8. Wait for the build (2–4 min). You'll get a URL like `https://synapse-frontend-xxxx.vercel.app` — **copy it**.
9. Update the `.env.prod` on your laptop so CORS matches:
   ```bash
   sed -i 's|^FRONTEND_URL=.*|FRONTEND_URL=https://<your-project>.vercel.app|; s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://<your-project>.vercel.app|' .env.prod
   ```
10. Open the Vercel URL — you should see the SYNAPSE login page (API calls will fail until Part 5, that's expected).

✅ **Part 3 done when:** the frontend loads at `*.vercel.app`.

---

## PART 4 — AI provider keys (≈15 min)

| Provider | Where | Key format | What you click |
|---|---|---|---|
| **Groq** (primary) | https://console.groq.com/keys | `gsk_...` | Sign in (GitHub/Google) → **API Keys** → **Create API Key** → name it `prod` → **Copy** |
| **NVIDIA NIM** (fallback) | https://build.nvidia.com | `nvapi-...` | Sign up → pick any model page → **Get API Key** → **Generate Key** → copy |
| **Gemini** (fallback) | https://aistudio.google.com/apikey | `AIza...` | Google account → **Create API key** → copy |

Paste all three into the laptop `.env.prod`:
```bash
sed -i 's|^GROQ_API_KEY=.*|GROQ_API_KEY=gsk_YOUR_KEY|; s|^NVIDIA_API_KEY=.*|NVIDIA_API_KEY=nvapi-YOUR_KEY|; s|^GEMINI_API_KEY=.*|GEMINI_API_KEY=AIzaYOUR_KEY|' .env.prod
```

✅ **Part 4 done when:** all three keys are in `.env.prod`.

---

## PART 5 — Configure GitHub deploy (laptop, 2 min)

1. In the repo directory on your laptop:
```bash
bash scripts/setup_github_deploy.sh <ORACLE_PUBLIC_IP> ubuntu synapse.duckdns.org
```
   What it does:
   - Generates a dedicated SSH key `~/.ssh/synapse_deploy` (never touches your personal key)
   - Sets GitHub **secrets**: `SSH_HOST`, `SSH_USER`, `SSH_PORT`, `SSH_KEY`, `NEXT_PUBLIC_API_URL`
   - Sets GitHub **variables**: `DEPLOY_ENABLED=true`, `PRODUCTION_URL=https://synapse.duckdns.org`
   - **Prints the public key** to paste into the box (next step)
2. Copy the printed `ssh-ed25519 AAAA...` line.

✅ **Part 5 done when:** it prints the public key.

---

## PART 6 — Bootstrap the box (30–60 min, mostly unattended build)

1. SSH to the box **in a new terminal** (keep the laptop terminal open for the next step):
```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@<YOUR_PUBLIC_IP>
```
2. Add the GitHub deploy public key (from Part 5):
```bash
echo 'ssh-ed25519 AAAA... synapse-cd@synapse.duckdns.org' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```
3. Run the bootstrap (this installs Docker, generates `.env.prod`, wires DuckDNS + Let's Encrypt, builds images natively, starts everything):
```bash
bash <(curl -sL https://raw.githubusercontent.com/Hayredin950/SYNAPSE/main/scripts/oracle_bootstrap.sh)
```
   - It asks for nothing; edit the top of the script only if your DuckDNS token differs — **default is fine if you'll set the token below**.
4. **Copy the laptop `.env.prod` up** (it has your Brevo + AI keys). From the laptop terminal:
```bash
scp -i ~/.ssh/id_ed25519 .env.prod ubuntu@<YOUR_PUBLIC_IP>:/tmp/.env.prod
```
   Then on the box:
```bash
sudo cp /tmp/.env.prod /opt/synapse/.env.prod
sudo chmod 600 /opt/synapse/.env.prod
```
   > The bootstrap generated its own `.env.prod` with random DB/Redis/Flower passwords — copying yours over keeps the Brevo/AI keys while retaining those random secrets **if you merge**. Simplest: after copying, verify DB/Redis passwords are still set:
   ```bash
   grep -E '^(DB_PASSWORD|REDIS_PASSWORD|FLOWER_PASSWORD)=' /opt/synapse/.env.prod
   ```
   If any are empty, re-copy them from the bootstrap-generated backup (`.env.prod.bak`).
5. Restart the stack so the new env takes effect:
```bash
cd /opt/synapse
docker compose -f docker-compose.prod.yml restart backend fastapi_ai celery_worker celery_beat
```
6. **Wait for the final health check line** in the bootstrap output — it curls `https://synapse.duckdns.org/api/v1/health/`.

✅ **Part 6 done when:** `curl https://synapse.duckdns.org/api/v1/health/` returns JSON with `"status":"ok"`.

---

## PART 7 — Final verification (10 min)

1. **Create your admin superuser** (on the box):
```bash
cd /opt/synapse
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```
2. **Admin panel:** open `https://synapse.duckdns.org/admin` and log in.
3. **Frontend:** open your `https://<your-project>.vercel.app` → register a test account → check your inbox for the Brevo verification email.
4. **Send a test email:**
```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.production')
django.setup()
from django.core.mail import send_mail
send_mail('SYNAPSE test', 'Deploy works!', 'SYNAPSE <noreply@synapse.ai>', ['sadim9812@gmail.com'])
print('sent')
"
```
5. **Confirm auto-deploy:** push any commit to `main` → GitHub Actions CD → "Deploy to Production" runs → hits your box, rebuilds, restarts. Watch it at `https://github.com/Hayredin950/SYNAPSE/actions`.

✅ **Done when:** register → email arrives → you're logged into the app served from your free stack.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `curl https://synapse.duckdns.org` times out | Port 80/443 not open in the Oracle Security List (Part 1.4) or DuckDNS A record wrong (Part 2.7) |
| certbot failed during bootstrap | DNS not resolving yet → wait 5 min, re-run: `certbot certonly --webroot -w /var/www/certbot -d synapse.duckdns.org` on the box, then `sudo cp /etc/letsencrypt/live/synapse.duckdns.org/{fullchain.pem,privkey.pem} /opt/synapse/infrastructure/nginx/certs/` |
| Health check 502 | Backend still starting (torch import takes 30–60s); wait and retry |
| Register → no email | `.env.prod` EMAIL_* values; run the test-send command (Part 7.4); check `docker compose logs backend \| grep -i error` |
| CD deploy job skipped | `DEPLOY_ENABLED` variable not `true`; re-run `bash scripts/setup_github_deploy.sh ...` |
| CD deploy fails SSH auth | Deploy key public half not in `~/.ssh/authorized_keys` on the box (Part 6.2) |
| Vercel build fails | Make sure Root Directory = `frontend` (Part 3.4) |
