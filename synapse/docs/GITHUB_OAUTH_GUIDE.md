# GitHub OAuth Configuration Guide

To manage both Local and Production environments for SYNAPSE, you should create **two separate GitHub OAuth Applications**. This is necessary because GitHub only allows one Authorization Callback URL per application.

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

- **Homepage URL:** `https://synapse-app-six.vercel.app`
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
