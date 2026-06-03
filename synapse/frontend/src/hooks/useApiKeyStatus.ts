/**
 * useApiKeyStatus
 * ~~~~~~~~~~~~~~~
 * Fetches whether the current user has configured their AI API keys.
 * Used to show a warning banner on AI-powered pages (Chat, Agents, etc.)
 * when no key is configured.
 */
import { useQuery } from '@tanstack/react-query'
import { api } from '@/utils/api'

interface ApiKeyStatus {
  gemini_configured: boolean
  openrouter_configured: boolean
  any_configured: boolean
}

export function useApiKeyStatus(): { status: ApiKeyStatus | null; isLoading: boolean } {
  const { data, isLoading } = useQuery<ApiKeyStatus>({
    queryKey: ['api-key-status'],
    queryFn: async () => {
      const res = await api.get('/users/ai-keys/')
      const d = res.data
      return {
        gemini_configured: !!d.gemini_configured,
        openrouter_configured: !!d.openrouter_configured,
        // Use the backend's authoritative value — it includes server-level env keys
        // (Replit AI gateway, OpenRouter env, Groq, etc.) so the banner only shows
        // when truly no AI backend is available at all.
        any_configured: !!(d.any_configured ?? d.gemini_configured ?? d.openrouter_configured),
      }
    },
    staleTime: 60_000,        // re-check once per minute
    retry: 1,
  })

  return { status: data ?? null, isLoading }
}
