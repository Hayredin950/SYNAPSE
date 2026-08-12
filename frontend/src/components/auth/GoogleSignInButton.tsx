/**
 * GoogleSignInButton
 * ~~~~~~~~~~~~~~~~~~
 * "Continue with Google" button using the SERVER-SIDE redirect flow
 * (identical to the GitHub button — no Google JS client script involved).
 *
 * The previous GSI implementation loaded https://accounts.google.com/gsi/client
 * in the browser. On networks where that script is blocked or silently dropped
 * (some ISPs/countries, ad-blockers), the button hung on "Loading Google
 * sign-in…" forever. The redirect flow avoids the script entirely:
 *
 *   1. Click → window.location.href = /api/v1/auth/google/redirect/
 *   2. Backend 302s to Google's consent screen (plain page navigation)
 *   3. Google redirects to /api/v1/auth/google/callback/?code=...
 *   4. Backend exchanges the code, creates/links the user, and redirects to
 *      /auth/google/success?access=...&refresh=...&is_onboarded=...
 *   5. The success page stores the JWT tokens and routes to /home or /wizard
 *
 * This works on any network that can load a normal Google page.
 */
'use client'

import { GoogleIcon } from './GoogleIcon'
import { withReferralParam } from '@/utils/referral'

export function GoogleSignInButton() {
  return (
    <button
      type="button"
      onClick={() => window.location.href = withReferralParam('/api/v1/auth/google/redirect/')}
      className="flex items-center justify-center gap-3 w-full py-3 rounded-xl text-sm font-medium transition-all duration-200
        border border-slate-200 hover:border-slate-300 bg-white hover:bg-slate-50 text-slate-700
        dark:border-white/10 dark:hover:border-white/20 dark:bg-white/5 dark:hover:bg-white/10 dark:text-slate-200
        shadow-sm"
    >
      <GoogleIcon />
      Continue with Google
    </button>
  )
}
