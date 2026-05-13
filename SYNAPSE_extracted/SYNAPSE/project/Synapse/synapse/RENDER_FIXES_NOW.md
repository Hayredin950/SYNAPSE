# Render — Fix These Env Vars Now

Based on the env vars currently set on your `synapse-api` service on Render,
here is the **exact** list of changes that will unblock email verification and
GitHub/Google login on production.

> The code in `backend/config/settings/production.py` now strips known
> placeholder values like `"value"`, `"your-key"`, `"change-me"`,
> `"noreply@yourdomain.com"` so they no longer poison downstream code. Bad
> values now read as missing instead of authenticating with junk.

---

## Critical (login / signup will not work without these)

### 1. `EMAIL_HOST_PASSWORD` is set to `value` — replace it

This is the placeholder Render auto-fills if you click **Generate** without
typing. Right now SMTP tries to authenticate against SendGrid with the literal
string `value` and gets rejected, so **no verification email is ever delivered.**

You have two paths. **Pick one:**

**Path A — SendGrid (recommended, takes ~5 minutes)**

1. Sign up free at <https://sendgrid.com> (100 emails/day free forever)
2. Settings → API Keys → Create API Key with "Mail Send" permission
3. Settings → Sender Authentication → verify a single sender (your email)
4. In Render, set:
   - `EMAIL_HOST_PASSWORD` = the SendGrid API key (starts with `SG.`)
   - `DEFAULT_FROM_EMAIL` = the email you verified in step 3
5. Save and redeploy

`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER` already default
to the right values for SendGrid — leave them alone.

**Path B — Firebase Admin SDK (since you wanted Firebase-only)**

The current Firebase setup on Render is **incomplete**: you have
`FIREBASE_PROJECT_ID` and `FIREBASE_WEB_API_KEY`, but the Admin SDK ALSO needs
service-account credentials to actually send emails server-side.

1. <https://console.firebase.google.com> → project `synapse-750`
2. Project Settings → **Service Accounts** → **Generate New Private Key**
3. Open the downloaded JSON file
4. Copy the **entire contents** (one line, with the `\n`s in the private key
   intact)
5. In Render, add a new env var:
   - Key: `FIREBASE_CREDENTIALS_JSON`
   - Value: paste the JSON string
6. Delete `EMAIL_HOST_PASSWORD` and `EMAIL_BACKEND` from Render entirely so
   the code falls back to Firebase
7. Save and redeploy

---

### 2. `DEFAULT_FROM_EMAIL` is set to `noreply@yourdomain.com` — replace it

SendGrid (and most SMTP providers) reject mail with an unverified sender
address. The placeholder is auto-discarded by the new code, but the app then
falls back to `noreply@synapse.ai` which you also don't own.

Set this to whatever email you verified in step 1.3 above. For Firebase
(Path B), this is ignored — Firebase sends from its own address.

---

## Cleanup (not breaking, but worth fixing)

### 3. `GEMINI_API_KEY` is set to `value`

You said this is fallback-only and users supply their own keys. The new code
already discards the placeholder so it won't break anything. **Either set a
real Google AI Studio key (free at <https://aistudio.google.com/apikey>) or
delete the env var entirely from Render.** Leaving the placeholder is harmless
now but generates noise in logs.

### 4. `JWT_SIGNING_KEY` is set but unused

Your `SIMPLE_JWT` config in `backend/config/settings/base.py` doesn't reference
`JWT_SIGNING_KEY`, so JWTs are actually signed with `SECRET_KEY` (which you
have set to a real random value — that's fine).

You can safely **delete `JWT_SIGNING_KEY` from Render** to reduce confusion.

### 5. `ALLOWED_HOSTS` includes the Vercel frontend URL

`synapse-app-six.vercel.app` belongs in `CORS_ALLOWED_ORIGINS` and
`CSRF_TRUSTED_ORIGINS` (where you already have it correctly), **not** in
`ALLOWED_HOSTS`. Django's `ALLOWED_HOSTS` is the set of hostnames that the
backend itself responds to — never the frontend.

Update `ALLOWED_HOSTS` on Render to:

```
synapse-api-oyld.onrender.com,localhost,127.0.0.1
```

(The line `srv-d7iv5h3bc2fs739bbpt0.render.com` is also unnecessary — Render
serves traffic only through your `*.onrender.com` hostname.)

---

## Required Render services that are still missing

These can't be fixed via env vars — you need to **add new services in the
Render dashboard**:

### Celery worker

Without this, scheduled scraping, agent runs, and async automation steps
never execute (the new sync-fallback in the trigger view only covers manually
triggered workflows; scheduled / event-driven runs still need the worker).

1. New → Background Worker
2. Same repo and branch as your web service
3. Build command: `pip install -r backend/requirements.txt`
4. Start command:
   `cd backend && celery -A config worker -l info --concurrency 2`
5. Copy **all** env vars from `synapse-api` (DATABASE_URL, REDIS_URL,
   CELERY_*, GOOGLE_*, etc.)

### Celery beat (scheduler)

1. New → Background Worker
2. Same repo + branch + build command as above
3. Start command:
   `cd backend && celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler`
4. Same env vars
5. **Important**: scale this to exactly 1 instance — running multiple beat
   schedulers will trigger every cron task multiple times.

---

## How to verify after redeploying

1. Visit <https://synapse-app-six.vercel.app/register>
2. Create an account with a real email
3. Check the email arrives within 30 seconds
4. Click the link, get redirected to `/verify-email?token=...`, account marked
   verified
5. Try GitHub login — the redirect should now end on `/home`, not on
   `/login?error=...`

If anything still fails, check Render → Logs and search for the string
`[Synapse]` — the new code emits a `RuntimeWarning` for every placeholder
env var it discards and explains what to set.
