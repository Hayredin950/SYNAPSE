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
| **Privacy policy link** | `https://synapse-one-blond.vercel.app/privacy` |
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

### ⚠️ Google branding verification — the domain ownership blocker

Google shows these errors on the **Branding** page:

> - The website of your home page URL is not registered to you.
> - Your home page does not explain the purpose of your app.
> - The app name "SYNAPSE" configured for your OAuth consent screen does not
>   match the app name on your home page.

**The root cause of ALL THREE is the same: `synapse-one-blond.vercel.app` is a
Vercel-owned subdomain (`*.vercel.app`), and Google cannot verify ownership of
a domain you don't control.** Google only accepts domains you own and have
verified in Google Search Console. `*.vercel.app` / `*.onrender.com` can never
pass — no DNS record or meta-tag trick works on a platform-owned subdomain.

**The fix (only you can do this):**

1. **Buy a real domain** you own, e.g. `synapse.app`, `getsynapse.com`, or
   `hayredin.dev` (any registrar: Namecheap, Cloudflare, Porkbun, …).
2. **Add it to Vercel:** project → Settings → Domains → add your domain and
   follow Vercel's DNS instructions. The app keeps working — Vercel serves it.
3. **Verify ownership in Google Search Console:**
   <https://search.google.com/search-console> → Add property → paste your
   domain → copy the DNS TXT record → add it at your registrar. (This is the
   step that makes the domain "registered to you" in Google's eyes.)
4. **Update the consent screen (Branding page):**
   - App home page → `https://<your-domain>`
   - Authorized domain → `<your-domain>` (the `vercel.app` entry can stay,
     but the homepage must be your own domain)
   - The app name `SYNAPSE` already matches the homepage hero text (fixed in
     the app) — keep both `SYNAPSE`.
5. Click **Request re-verification** on the Branding page.

**About the other two errors:**
- *"home page does not explain the purpose"* → the landing page hero now
  states the purpose explicitly ("SYNAPSE is an AI-powered technology
  intelligence platform…") and the app name in the H1 — this satisfies the
  requirement once the domain is verified.
- *"app name does not match"* → the homepage headline now reads **SYNAPSE**
  prominently, matching the consent screen name exactly.

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
