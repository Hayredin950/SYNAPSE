# GitHub OAuth Configuration Guide

To manage both Local and Production environments for SYNAPSE, you should create **two separate GitHub OAuth Applications**. This is necessary because GitHub only allows one Authorization Callback URL per application.

## 0. Brand the OAuth application (do this first)

The GitHub authorization page is GitHub-hosted, but it displays **your app's
name, description and logo** from the OAuth App settings. If those are unset,
users see a generic screen and the raw Render URL — the same problem the
Google account chooser had.

For **each** OAuth application (`SYNAPSE - Local` and `SYNAPSE - Production`),
open **GitHub → Settings → Developer settings → OAuth Apps → your app →
Edit**, then set:

- **Application name:** `SYNAPSE` (or `SYNAPSE - Local` for dev)
- **Homepage URL:**
  - Local: `http://localhost:3000`
  - Production: `https://synapse-one-blond.vercel.app`
- **Application description:**
  `AI-powered technology intelligence, research, and automation platform.`
- **Application logo:** upload `docs/branding/github-oauth-logo.png`
  (512×512, white circle + emblem — GitHub shows it in a circular frame on
  the authorize page). A transparent variant is available at
  `docs/branding/github-oauth-logo-transparent.png`.
- **Authorization callback URL:** as in sections 1–2 below.

GitHub caches app metadata, so after editing, hard-refresh (or open an
incognito window) to see the new name/logo on the authorize screen.

> **Note:** GitHub does not let you change the domain that appears in the
> authorize page URL — that is always `github.com/login/oauth/authorize`. The
> branding above (name + logo + description) is what makes the page look
> professional.

## 1. Local Environment (Development)

**GitHub App Name:** `SYNAPSE - Local`

- **Homepage URL:** `http://localhost:3000`
- **Authorization callback URL:** `http://localhost:8000/api/v1/auth/github/callback/`

**Local `.env` Configuration:**
```env
GITHUB_CLIENT_ID=your_local_client_id
GITHUB_CLIENT_SECRET=your_local_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/auth/github/callback/
```

---

## 2. Production Environment (Render/Vercel)

**GitHub App Name:** `SYNAPSE - Production`

- **Homepage URL:** `https://synapse-one-blond.vercel.app`
- **Authorization callback URL:** `https://srv-d7iv5h3bc2fs739bbpt0.render.com/api/v1/auth/github/callback/`

**Production `.env` Configuration (on Render):**
```env
GITHUB_CLIENT_ID=your_production_client_id
GITHUB_CLIENT_SECRET=your_production_client_secret
GITHUB_REDIRECT_URI=https://srv-d7iv5h3bc2fs739bbpt0.render.com/api/v1/auth/github/callback/
```

---

## How it works
The backend logic in `backend/apps/users/github_views.py` uses the `GITHUB_REDIRECT_URI` environment variable. By setting this correctly on each platform, the application will automatically use the correct callback for that environment.

1. When you click "Login with GitHub", the backend sends the user to GitHub with the `redirect_uri` from your `.env`.
2. GitHub verifies that this `redirect_uri` matches the one configured in the GitHub App associated with the `GITHUB_CLIENT_ID`.
3. After approval, GitHub sends the user back to that URI.
