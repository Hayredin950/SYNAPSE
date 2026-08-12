/**
 * referral.ts — referral-link plumbing shared by every signup path.
 *
 * The referral link looks like https://<frontend>/register?ref=ABCD1234.
 * The code must survive the whole signup journey (email or OAuth) and then
 * be POSTed to /growth/referral/ once the user is authenticated.
 *
 *   - captureReferralCode(ref)  — called when a page loads with ?ref= (register,
 *                                 login, or an OAuth success page that received
 *                                 the code back through the provider's state).
 *   - getPendingReferralCode()  — read the stashed code from localStorage.
 *   - applyPendingReferral()    — fire-and-forget: POSTs the code to the backend
 *                                 after signup/login succeeds, then clears it.
 */

const PENDING_REF_KEY = 'synapse_pending_ref'

/** Store a referral code so it can be applied after signup completes. */
export function captureReferralCode(ref: string | null | undefined): void {
  if (!ref) return
  const code = ref.trim().toUpperCase().slice(0, 12)
  if (!code) return
  try {
    localStorage.setItem(PENDING_REF_KEY, code)
  } catch {
    /* private mode — ignore */
  }
}

/** Read the stashed pending referral code (null if none). */
export function getPendingReferralCode(): string | null {
  try {
    return localStorage.getItem(PENDING_REF_KEY)
  } catch {
    return null
  }
}

/** Append ?ref=… to an OAuth start URL when a pending code exists. */
export function withReferralParam(url: string): string {
  const code = getPendingReferralCode()
  if (!code) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}ref=${encodeURIComponent(code)}`
}

/**
 * Apply the pending referral code to the authenticated user.
 * Best-effort: failures are silent — a wrong/expired code must never block
 * the user's first-run experience. Clears the stash once applied.
 */
export async function applyPendingReferral(): Promise<void> {
  const code = getPendingReferralCode()
  if (!code) return

  try {
    const { api } = await import('@/utils/api')
    await api.post('/growth/referral/', { code })
  } catch {
    // Referral bonus is a nice-to-have — never surface an error for it.
  } finally {
    try {
      localStorage.removeItem(PENDING_REF_KEY)
    } catch {
      /* ignore */
    }
  }
}
