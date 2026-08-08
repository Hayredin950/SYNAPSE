'use client'
// Documents merged into Agents page — redirect transparently
// Also handles Google Drive OAuth callback via postMessage
import { useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

export default function DocumentsRedirect() {
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    const driveConnected = searchParams.get('drive_connected')
    const driveError = searchParams.get('drive_error')

    // Handle OAuth callback by sending postMessage to parent window
    if (driveConnected === 'true' || driveError) {
      if (window.opener) {
        window.opener.postMessage(
          { type: 'drive-oauth-complete', success: driveConnected === 'true' },
          window.location.origin
        )
        // Close the popup after sending the message
        window.close()
      }
    } else {
      // Normal redirect to agents page
      router.replace('/agents')
    }
  }, [searchParams, router])

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50 dark:bg-slate-950">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-600 dark:text-slate-400 text-sm">Completing OAuth...</p>
      </div>
    </div>
  )
}
