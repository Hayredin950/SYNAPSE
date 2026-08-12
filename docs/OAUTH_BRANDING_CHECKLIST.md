# OAuth Branding Checklist — Google + GitHub

Follow this top-to-bottom, in both consoles. Everything in code is already in
place — these are the only manual steps left.

> **Quick reference**
> - Frontend: `https://synapse-one-blond.vercel.app`
> - Backend: `https://synapse-backend-z9bb.onrender.com`
> - Logo assets: `docs/branding/*.png`

---

## Part 1 — Google (account chooser dialog)

**1. Brand the OAuth consent screen**
Open <https://console.cloud.google.com/apis/credentials/consent>
(select the project that owns your `GOOGLE_CLIENT_ID`), then:

| Field | Value |
|---|---|
| App name | `SYNAPSE` |
| Support email | `hayredin.950@gmail.com` |
| Logo | upload `docs/branding/google-consent-logo.png` |
| App domain → Authorized domain | `synapse-backend-z9bb.onrender.com` |
| App homepage link | `https://synapse-one-blond.vercel.app` |
| Audience | switch from **Testing** to **In production** |

**2. Add the exact redirect URIs**
Open <https://console.cloud.google.com/apis/credentials> → your OAuth 2.0
Client ID → **Authorized redirect URIs** — paste ALL of these:

```
https://synapse-backend-z9bb.onrender.com/api/v1/auth/google/callback/
https://synapse-backend-z9bb.onrender.com/api/v1/integrations/drive/callback/
```

**Authorized JavaScript origins** (same page):

```
https://synapse-one-blond.vercel.app
```

> If you later add a custom domain (e.g. `api.synapse.app`) to Render,
> replace `synapse-backend-z9bb.onrender.com` with it in both places and set
> `GOOGLE_REDIRECT_URI=https://api.synapse.app/api/v1/auth/google/callback/`
> on Render.

**3. Confirm env vars on Render (backend service)**
```
GOOGLE_CLIENT_ID=<your client id>
GOOGLE_CLIENT_SECRET=<your secret>
```
The code (`backend/apps/users/google_views.py`) auto-derives the redirect URI
from the request host, so a `GOOGLE_REDIRECT_URI` env var is optional as long
as the hosts above match.

**Done →** the dialog now shows **SYNAPSE** + your logo, and users can sign in
(no more "testing mode" block).

---

## Part 2 — GitHub (authorize page)

Open **GitHub → Settings → Developer settings → OAuth Apps** and edit **both**
apps (`SYNAPSE - Local`, `SYNAPSE - Production`):

| Field | Production | Local |
|---|---|---|
| Application name | `SYNAPSE` | `SYNAPSE - Local` |
| Homepage URL | `https://synapse-one-blond.vercel.app` | `http://localhost:3000` |
| Description | `AI-powered technology intelligence, research, and automation platform.` | (same) |
| Logo | upload `docs/branding/github-oauth-logo.png` | (same) |
| Authorization callback URL | see below | `http://localhost:8000/api/v1/auth/github/callback/` |

**Production callback URL — paste exactly:**

```
https://synapse-backend-z9bb.onrender.com/api/v1/auth/github/callback/
```

**Confirm env vars on Render:**
```
GITHUB_CLIENT_ID=<your production client id>
GITHUB_CLIENT_SECRET=<your production secret>
GITHUB_REDIRECT_URI=https://synapse-backend-z9bb.onrender.com/api/v1/auth/github/callback/
```

**Done →** the authorize page shows the SYNAPSE name, description and logo.
(Note: GitHub always shows `github.com/login/oauth/authorize` in the address
bar — the branding above is what makes the page look professional.)

---

## Part 3 — Verify

1. **Google:** open an incognito window → `https://synapse-one-blond.vercel.app/login` → **Continue with Google**. You should see **SYNAPSE** + your logo in the account chooser, and the sign-in completes (no test-user error).
2. **GitHub:** same page → **Continue with GitHub** → authorize page shows SYNAPSE branding.
3. If Google still looks unchanged, hard-refresh / wait ~1h (Google caches consent-screen branding), then re-check.
