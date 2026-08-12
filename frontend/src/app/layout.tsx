import type { Metadata, Viewport } from 'next'
import { Providers } from '@/components/Providers'
import { FocusModeProvider } from '@/components/ui/FocusMode'
import { ServiceWorkerRegistration } from '@/components/ServiceWorkerRegistration'
import { RateLimitBanner } from '@/components/RateLimitBanner'
import { PWAUpdateBanner } from '@/components/ui/PWAUpdateBanner'
import '@/styles/globals.css'
import 'katex/dist/katex.min.css'

// Use system font stack instead of fetching from Google Fonts (avoids network timeout in dev)
const inter = { variable: '--font-inter' }

// Viewport config must be a separate export in Next.js 14+
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: '#6366f1',
}

export const metadata: Metadata = {
  title: { default: 'SYNAPSE', template: '%s | SYNAPSE' },
  description: 'AI-Powered Technology Intelligence Platform — discover, research, and automate with AI.',
  keywords: ['AI', 'technology', 'intelligence', 'machine learning', 'research', 'automation'],
  metadataBase: new URL('https://synapse-one-blond.vercel.app'),
  manifest: '/manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'SYNAPSE',
  },
  icons: {
    icon: [
      { url: '/icons/icon-192x192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icons/icon-512x512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: '/icons/icon-192x192.png',
  },
  openGraph: {
    title: 'SYNAPSE — AI-Powered Tech Intelligence',
    description: 'Your personal AI-curated feed of articles, papers, repos, and videos — all searchable and summarized. AI agents that research, summarize, and automate.',
    url: 'https://synapse-one-blond.vercel.app',
    siteName: 'SYNAPSE',
    type: 'website',
    locale: 'en_US',
    images: [
      {
        url: '/opengraph-image.png',
        width: 1200,
        height: 630,
        alt: 'SYNAPSE — AI-Powered Technology Intelligence',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'SYNAPSE — AI-Powered Tech Intelligence',
    description: 'Your personal AI-curated feed of articles, papers, repos, and videos — all searchable and summarized.',
    images: ['/twitter-image.png'],
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className="h-full" data-scroll-behavior="smooth">
      <body className={`${inter.variable} h-full bg-slate-50 dark:bg-slate-900 transition-colors duration-300`}>
        {/* TASK-405-5: Skip-to-main-content link for keyboard/screen-reader users */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 z-[200] focus:px-4 focus:py-2 focus:bg-indigo-600 focus:text-white focus:rounded-lg focus:font-medium focus:text-sm focus:shadow-lg"
        >
          Skip to content
        </a>
        <ServiceWorkerRegistration />
        <Providers>
          <FocusModeProvider>
            {children}
          </FocusModeProvider>
        </Providers>
        {/* TASK-501-F1: Rate limit exceeded banner with countdown + upgrade CTA */}
        <RateLimitBanner />
        {/* Feature #20: PWA Service Worker update notification */}
        <PWAUpdateBanner />
        {/* TASK-104-3: Portal root for React modal portals */}
        <div id="modal-root" />
      </body>
    </html>
  )
}
