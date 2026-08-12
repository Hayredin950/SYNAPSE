# Google OAuth Branding Guide

When a user clicks **Continue with Google**, they see Google's account chooser:

> **Choose an account** to continue to synapse-backend-z9bb.onrender.com

That dialog is **hosted by Google** — its buttons, colors and layout cannot be
restyled by your app. However, everything that makes it look generic *is*
configurable in the **Google Cloud Console**:

1. The **app name** shown in the dialog header.
2. The **logo** shown next to it.
3. The **"continue to …" domain** — currently the raw Render URL.

Branding your OAuth consent screen turns that plain dialog into:

> **SYNAPSE** — AI-Powered Tech Intelligence
> **Choose an account** to continue to **api.synapse.app**

---

## 1. Brand the OAuth consent screen

1. Go to <https://console.cloud.google.com/apis/credentials/consent> and select
   the project that owns the `GOOGLE_CLIENT_ID` used by your backend.
2. Under **Branding**:
   - **App name:** `SYNAPSE`
   - **Support email:** your email (e.g. `hayredin.950@gmail.com`)
   - **Logo:** upload `docs/branding/google-consent-logo.png`
     (512×512, white circle + emblem — renders nicely in Google's circular frame).
     A transparent variant is also available:
     `docs/branding/google-consent-logo-transparent.png`
   - **App domain — Authorized domain:** add your **backend domain** so Google
     shows a friendly name instead of the raw URL (see step 2).
   - **App homepage link:** `https://synapse-one-blond.vercel.app`
3. Under **Audience**, switch the app from *Testing* to **In production** so
   every user can sign in (Testing mode only allows listed test users).
4. Save, then re-test the login flow. The account chooser now shows the
   **SYNAPSE** name and logo.

## 2. Fix the "continue to synapse-backend-z9bb.onrender.com" text

That domain comes from the host of your OAuth **redirect URI** — the
`onrender.com` URL is what your OAuth client was created with. Google shows
whatever host is registered. To make it attractive:

**Option A — add a custom domain to Render (recommended, changes the text):**
1. Buy a domain (e.g. `synapse.app` or `api.synapse.app`).
2. In Render, add the custom domain to your backend service
   (Dashboard → your backend → Settings → Custom Domains) and point the DNS
   record at Render.
3. In the Google Cloud Console → **APIs & Services → Credentials → your OAuth
   2.0 Client ID**, add:
   - **Authorized JavaScript origins:** `https://synapse-one-blond.vercel.app`
   - **Authorized redirect URIs:**
     - `https://api.synapse.app/api/v1/auth/google/callback/`
4. On Render, set the environment variable:
   ```
   GOOGLE_REDIRECT_URI=https://api.synapse.app/api/v1/auth/google/callback/
   ```
   (`backend/apps/users/google_views.py` prefers this env var over deriving
   the host, so the callback always matches what's registered.)
5. Add `api.synapse.app` (or your custom domain) under
   **OAuth consent screen → App domain → Authorized domain**.

The dialog now reads **"continue to api.synapse.app"**.

**Option B — no custom domain (logo/name only):**
The account chooser will keep showing the Render host, but the SYNAPSE name,
logo and support email from step 1 still make it look polished.

---

## Environment variables

| Variable | Where | Example |
|---|---|---|
| `GOOGLE_CLIENT_ID` | Render | `1234….apps.googleusercontent.com` |
| `GOOGLE_CLIENT_SECRET` | Render | `GOCSPX-…` |
| `GOOGLE_REDIRECT_URI` | Render | `https://api.synapse.app/api/v1/auth/google/callback/` |

The same `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` are shared by the Google
Drive integration (`backend/apps/integrations/google_drive.py`), so when you
edit the OAuth client's redirect URIs, keep the Drive callback registered too
(mounted at `/api/v1/integrations/`):

```
https://api.synapse.app/api/v1/integrations/drive/callback/
```

---

## Local development

For local testing, create a **separate OAuth client** (Google only allows one
redirect URI set per client — same constraint as GitHub):

- **Authorized redirect URI:** `http://localhost:8000/api/v1/auth/google/callback/`

```env
GOOGLE_CLIENT_ID=your_local_client_id
GOOGLE_CLIENT_SECRET=your_local_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback/
```

---

## How it works

`backend/apps/users/google_views.py`:

1. `GET /api/v1/auth/google/redirect/` → 302 to Google's OAuth consent screen.
2. Google shows the account chooser with your **branded app name + logo**
   (from the consent screen config) and the **host of the redirect URI**.
3. `GET /api/v1/auth/google/callback/` exchanges the code, creates/links the
   user, and redirects to the frontend with JWT tokens.

Since the button uses a plain server-side redirect (no Google JS), branding
only needs the console config above — no code changes required.
