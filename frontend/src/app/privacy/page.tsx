import Link from 'next/link'
import type { Metadata } from 'next'
import { LogoMark } from '@/components/ui/Logo'

export const metadata: Metadata = {
  title: 'Privacy Policy',
  description: 'SYNAPSE privacy policy — how we collect, use, and protect your data.',
}

const SECTIONS = [
  {
    title: '1. Information We Collect',
    body: 'We collect the minimum information needed to run SYNAPSE. When you create an account we store your email address and profile details. If you sign in with Google or GitHub, we store your provider ID, email, name, and avatar URL. Content you generate (chat messages, agent runs, generated documents) is stored to provide and improve the service. We never sell your personal data.',
  },
  {
    title: '2. How We Use Your Data',
    body: 'Your data is used to: authenticate you and personalize your feed, run AI chat and agent requests you initiate, send transactional emails (verification, password reset, workflow notifications), and keep the service secure. AI requests may be sent to third-party AI providers (e.g. OpenRouter, Gemini) to generate responses — only the content of your request is transmitted, never your password or billing details.',
  },
  {
    title: '3. Cookies & Local Storage',
    body: 'SYNAPSE uses local storage to keep you signed in and remember preferences (theme, reading goals, reader settings). We use standard web analytics to understand aggregate usage. You can clear this data at any time from your browser settings; doing so may sign you out.',
  },
  {
    title: '4. Third-Party Services',
    body: 'We integrate with third-party services you choose to connect: GitHub (OAuth sign-in and starred-repo sync), Google (OAuth sign-in and Google Drive export), and AI providers for generation. Each integration only receives the data required for the specific feature. We are not responsible for the privacy practices of these third parties.',
  },
  {
    title: '5. Data Retention',
    body: 'We retain your data while your account is active. You may delete your account at any time, which removes your personal information and generated content from our systems. Backups may retain data temporarily and are purged on a rolling schedule.',
  },
  {
    title: '6. Your Rights',
    body: 'Depending on your jurisdiction (including GDPR and CCPA), you may have the right to access, correct, export, or delete your personal data. Contact us and we will honor your request within 30 days. You can also disconnect third-party integrations (Google Drive, GitHub) from your settings at any time.',
  },
  {
    title: '7. Security',
    body: 'We use industry-standard protections: HTTPS everywhere, password hashing with Argon2/bcrypt, JWT-based authentication, and least-privilege access to servers and databases. No method of transmission is 100% secure, but we work to protect your data against unauthorized access.',
  },
  {
    title: '8. Children',
    body: 'SYNAPSE is not directed at children under 13. We do not knowingly collect personal information from children. If you believe a child has provided us personal data, contact us and we will delete it.',
  },
  {
    title: '9. Changes to This Policy',
    body: 'We may update this policy from time to time. Material changes will be announced on the app and take effect immediately. Continued use of SYNAPSE after changes constitutes acceptance of the updated policy.',
  },
  {
    title: '10. Contact',
    body: 'Questions about this policy or your data? Email us at hayredin.950@gmail.com or open an issue on our GitHub repository. We typically respond within 2 business days.',
  },
]

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950 text-slate-900 dark:text-white">
      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-white/80 dark:bg-slate-950/80 backdrop-blur-xl border-b border-slate-200/60 dark:border-slate-800/60">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2.5">
            <LogoMark size={28} />
            <span className="font-black text-lg tracking-tight bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
              SYNAPSE
            </span>
          </Link>
          <Link href="/"
            className="text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
            ← Back to home
          </Link>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 py-16">
        <div className="mb-12">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 border border-indigo-200 dark:border-indigo-500/30 text-indigo-700 dark:text-indigo-300 text-xs font-semibold mb-6">
            Legal
          </div>
          <h1 className="text-4xl sm:text-5xl font-black tracking-tight mb-4">Privacy Policy</h1>
          <p className="text-slate-600 dark:text-slate-400 text-lg">
            Last updated: August 12, 2026
          </p>
          <p className="mt-6 text-slate-600 dark:text-slate-400 leading-relaxed">
            SYNAPSE (&quot;we&quot;, &quot;our&quot;, &quot;us&quot;) is an AI-powered technology
            intelligence platform. This policy explains what data we collect, how we use it, and
            the choices you have. By using SYNAPSE you agree to the practices described here.
          </p>
        </div>

        <div className="space-y-8">
          {SECTIONS.map((s) => (
            <section key={s.title}>
              <h2 className="text-xl font-bold mb-3">{s.title}</h2>
              <p className="text-slate-600 dark:text-slate-400 leading-relaxed">{s.body}</p>
            </section>
          ))}
        </div>

        <div className="mt-16 p-6 rounded-2xl bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="font-semibold mb-1">Questions about your data?</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              We&apos;re happy to help — reach out anytime.
            </p>
          </div>
          <div className="flex gap-3">
            <a href="mailto:hayredin.950@gmail.com"
              className="inline-flex items-center gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 text-white text-sm font-semibold px-5 py-2.5 rounded-xl hover:opacity-90 transition-opacity">
              Contact us
            </a>
            <a href="https://github.com/Hayredin950" target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-sm font-semibold px-5 py-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
              GitHub
            </a>
          </div>
        </div>
      </main>

      <footer className="border-t border-slate-200 dark:border-slate-800 py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center text-xs text-slate-500">
          © {new Date().getFullYear()} SYNAPSE · AI-Powered Technology Intelligence
        </div>
      </footer>
    </div>
  )
}
