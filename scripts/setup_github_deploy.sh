#!/usr/bin/env bash
# ============================================================
# SYNAPSE — Configure GitHub Actions deploy secrets/vars
# ============================================================
# Run ONCE from your laptop (the machine with gh authenticated)
# AFTER the Oracle box exists:
#
#   bash scripts/setup_github_deploy.sh 123.456.789.10
#
# Args:
#   $1  Oracle box public IP (required)
#   $2  SSH user on the box        (default: ubuntu)
#   $3  DuckDNS API domain         (default: synapseai.duckdns.org)
#   $4  Vercel frontend URL        (default: https://synapse-app-six.vercel.app)
#
# What it does:
#   1. Generates a dedicated deploy keypair (~/.ssh/synapse_deploy_*)
#      — NEVER reuses your personal key
#   2. Sets GitHub Actions SECRETS: SSH_HOST, SSH_USER, SSH_KEY, SSH_PORT,
#      NEXT_PUBLIC_API_URL
#   3. Sets GitHub Actions VARIABLES: DEPLOY_ENABLED=true, PRODUCTION_URL
#   4. Prints the PUBLIC key — paste it into the box's
#      ~/.ssh/authorized_keys (the bootstrap script also prints this)
# ============================================================

set -euo pipefail

BOX_IP="${1:?Usage: $0 <box-ip> [ssh-user] [domain] [app-url]}"
SSH_USER="${2:-ubuntu}"
DOMAIN="${3:-synapseai.duckdns.org}"
APP_URL="${4:-https://synapse-app-six.vercel.app}"

echo "=== Configuring GitHub deploy secrets for ${DOMAIN} @ ${SSH_USER}@${BOX_IP} ==="

# ── 1. Deploy keypair ─────────────────────────────────────────────────────────
KEY_PATH="$HOME/.ssh/synapse_deploy"
if [ ! -f "$KEY_PATH" ]; then
  ssh-keygen -t ed25519 -N "" -C "synapse-cd@${DOMAIN}" -f "$KEY_PATH" >/dev/null
  echo "  ✓ Generated deploy key: ${KEY_PATH}"
else
  echo "  · Reusing existing deploy key: ${KEY_PATH}"
fi

# ── 2. Secrets ────────────────────────────────────────────────────────────────
gh secret set SSH_HOST --body "$BOX_IP"
gh secret set SSH_USER --body "$SSH_USER"
gh secret set SSH_PORT --body "22"
gh secret set SSH_KEY --body "$(cat "$KEY_PATH")"
gh secret set NEXT_PUBLIC_API_URL --body "https://${DOMAIN}"
echo "  ✓ Secrets set: SSH_HOST, SSH_USER, SSH_PORT, SSH_KEY, NEXT_PUBLIC_API_URL"

# ── 3. Variables (public, not secret) ─────────────────────────────────────────
gh variable set DEPLOY_ENABLED --body "true"
gh variable set PRODUCTION_URL --body "https://${DOMAIN}"
echo "  ✓ Variables set: DEPLOY_ENABLED=true, PRODUCTION_URL=https://${DOMAIN}"

# ── 4. Print the public key for the box ───────────────────────────────────────
echo ""
echo "============================================================"
echo " Add this PUBLIC key to the Oracle box:"
echo "   echo '$(cat "$KEY_PATH.pub")' >> ~/.ssh/authorized_keys"
echo ""
echo " Then push to main — the CD pipeline will build + deploy."
echo "============================================================"
