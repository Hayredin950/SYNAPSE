'use client';

/**
 * TASK-605-F2: Developer Portal page
 * Route: /developers
 *
 * Sections:
 *  1. Quick Start — copy-paste code snippets (Python / TypeScript / cURL)
 *  2. Rate Limits table — limits per plan tier
 *  3. SDK Downloads — pip + npm install commands
 *  4. Link to Swagger/ReDoc docs
 */

import React, { useState } from 'react';
import { Code, Copy, Check, ExternalLink, Key, Zap, Package, BookOpen, Terminal } from 'lucide-react';
import Link from 'next/link';
import toast from 'react-hot-toast';

// ── Copy button ────────────────────────────────────────────────────────────────

function CopyButton({ text, className = '' }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button onClick={copy}
      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
        copied
          ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400'
          : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
      } ${className}`}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

// ── Code block ─────────────────────────────────────────────────────────────────

function CodeBlock({ code, language }: { code: string; language: string }) {
  return (
    <div className="relative bg-slate-950 rounded-xl overflow-hidden border border-slate-800">
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
        <span className="text-xs font-mono text-slate-400">{language}</span>
        <CopyButton text={code} />
      </div>
      <pre className="px-4 py-3 text-xs text-slate-300 font-mono overflow-x-auto whitespace-pre leading-relaxed">
        {code}
      </pre>
    </div>
  );
}

// ── Snippets ───────────────────────────────────────────────────────────────────

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.synapse.app';

const SNIPPETS = {
  python: `import requests

API_KEY = "sk-syn-your-api-key-here"
BASE_URL = "${BASE_URL}"

headers = {"Authorization": f"Bearer {API_KEY}"}

# Search articles
resp = requests.get(f"{BASE_URL}/api/v1/content/articles/",
    headers=headers, params={"q": "LLM fine-tuning", "limit": 10})
articles = resp.json()["data"]

# Ask AI
resp = requests.post(f"{BASE_URL}/api/v1/ai/query/",
    headers=headers, json={"question": "What is RAG?"})
print(resp.json()["data"]["answer"])`,

  typescript: `const API_KEY = "sk-syn-your-api-key-here";
const BASE_URL = "${BASE_URL}";

const headers = { Authorization: \`Bearer \${API_KEY}\` };

// Search papers
const resp = await fetch(\`\${BASE_URL}/api/v1/content/papers/?q=transformers\`, { headers });
const { data } = await resp.json();

// Ask AI
const aiResp = await fetch(\`\${BASE_URL}/api/v1/ai/query/\`, {
  method: "POST",
  headers: { ...headers, "Content-Type": "application/json" },
  body: JSON.stringify({ question: "Explain diffusion models" }),
});
const { data: { answer } } = await aiResp.json();`,

  curl: `# Set your API key
export SYNAPSE_KEY="sk-syn-your-api-key-here"

# Search articles
curl -H "Authorization: Bearer $SYNAPSE_KEY" \\
  "${BASE_URL}/api/v1/content/articles/?q=rust+async"

# Ask AI
curl -X POST -H "Authorization: Bearer $SYNAPSE_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"question":"What is the attention mechanism?"}' \\
  "${BASE_URL}/api/v1/ai/query/"

# Get trending
curl -H "Authorization: Bearer $SYNAPSE_KEY" \\
  "${BASE_URL}/api/v1/trends/"`,
};

// ── Main page ──────────────────────────────────────────────────────────────────

export default function DeveloperPortalPage() {
  const [lang, setLang] = useState<'python' | 'typescript' | 'curl'>('python');

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="pb-16">

        {/* ── Hero header ── */}
        <div className="px-6 pt-8 pb-8 border-b border-slate-200 dark:border-slate-800 bg-gradient-to-br from-indigo-50/60 via-white to-white dark:from-indigo-950/20 dark:via-slate-950 dark:to-slate-950">
          <div className="max-w-3xl">
            <div className="flex items-center gap-2 text-indigo-500 text-sm font-semibold mb-3">
              <Code size={16} />
              Developer Portal
            </div>
            <h1 className="text-4xl font-black text-slate-900 dark:text-white tracking-tight">
              Build with the Synapse API
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg leading-relaxed">
              Access 100K+ articles, papers, repositories, and AI-powered search via a simple REST API.
            </p>
            <div className="flex items-center gap-3 mt-5">
              <Link href="/settings"
                className="flex items-center gap-2 px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white text-sm font-semibold rounded-xl transition-colors shadow-sm">
                <Key size={15} />
                Get API Key
              </Link>
              <a href={`${BASE_URL}/api/schema/redoc/`} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 text-sm font-semibold rounded-xl hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                <BookOpen size={15} />
                API Reference
                <ExternalLink size={12} className="text-slate-400" />
              </a>
            </div>
          </div>
        </div>

        <div className="px-6 mt-10 max-w-4xl space-y-12">

          {/* ── Section 1: Quick Start ── */}
          <section>
            <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-1 flex items-center gap-2">
              <Terminal size={20} className="text-indigo-500" />
              Quick Start
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm mb-5">
              Get up and running in under 5 minutes. Grab your API key from{' '}
              <Link href="/settings" className="text-indigo-500 hover:underline">Settings → API Keys</Link>.
            </p>

            {/* Language tabs */}
            <div className="flex items-center gap-1.5 mb-4 bg-slate-100 dark:bg-slate-800 rounded-xl p-1 w-fit">
              {(['python', 'typescript', 'curl'] as const).map(l => (
                <button key={l} onClick={() => setLang(l)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    lang === l
                      ? 'bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 shadow-sm'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-700'
                  }`}>
                  {l === 'typescript' ? 'TypeScript' : l.charAt(0).toUpperCase() + l.slice(1)}
                </button>
              ))}
            </div>

            <CodeBlock code={SNIPPETS[lang]} language={lang === 'typescript' ? 'TypeScript' : lang === 'python' ? 'Python' : 'cURL'} />
          </section>

          {/* ── Section 2: Endpoints ── */}
          <section>
            <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-1 flex items-center gap-2">
              <Zap size={20} className="text-amber-500" />
              API Endpoints
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm mb-5">All endpoints return JSON with <code className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">{"{ success, data, count }"}</code>.</p>

            <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-700">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-700">
                    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-200">Method</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-200">Endpoint</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-200">Description</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-200">Params</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {[
                    { method: 'GET',  path: '/api/v1/content/articles/', desc: 'Search articles',    params: '?q, ?topic, ?limit' },
                    { method: 'GET',  path: '/api/v1/content/papers/',   desc: 'Search papers',      params: '?q, ?limit' },
                    { method: 'GET',  path: '/api/v1/content/repos/',    desc: 'Search repos',       params: '?q, ?language, ?limit' },
                    { method: 'POST', path: '/api/v1/ai/query/',         desc: 'Ask AI (RAG)',        params: 'body: {question}' },
                    { method: 'GET',  path: '/api/v1/trends/',           desc: 'Trending content',   params: '?limit' },
                    { method: 'POST', path: '/api/v1/content/save/',     desc: 'Save URL to library',params: 'body: {url, title, tags}' },
                    { method: 'GET',  path: '/api/v1/users/keys/',       desc: 'List API keys',      params: '—' },
                    { method: 'POST', path: '/api/v1/users/keys/',       desc: 'Create API key',     params: 'body: {name, scopes}' },
                    { method: 'DELETE', path: '/api/v1/users/keys/{id}/',desc: 'Revoke API key',     params: '—' },
                  ].map(row => (
                    <tr key={row.path} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-bold ${
                          row.method === 'GET'    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' :
                          row.method === 'POST'   ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                          'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        }`}>
                          {row.method}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-700 dark:text-slate-200">{row.path}</td>
                      <td className="px-4 py-3 text-slate-600 dark:text-slate-300">{row.desc}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-400">{row.params}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ── Section 3: Rate Limits ── */}
          <section>
            <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-1 flex items-center gap-2">
              <Zap size={20} className="text-orange-500" />
              Rate Limits
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm mb-5">
              Rate limits are enforced per API key. Exceeded limits return <code className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">HTTP 429</code> with <code className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">Retry-After</code> and <code className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">X-RateLimit-Reset</code> headers.
            </p>

            <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-700">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-700">
                    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-200">Plan</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-200">API Requests</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-200">AI Chat</th>
                    <th className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-200">Agent Tasks</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {[
                    { plan: 'Free',       badge: 'bg-slate-100 text-slate-600', api: '100 / hour',  chat: '5 / day',    agent: '1 / day'   },
                    { plan: 'Pro',        badge: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400', api: '500 / hour',  chat: '200 / day',  agent: '50 / day'  },
                    { plan: 'Enterprise', badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',   api: '2000 / hour', chat: '1000 / day', agent: '200 / day' },
                  ].map(row => (
                    <tr key={row.plan} className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${row.badge}`}>{row.plan}</span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-700 dark:text-slate-200">{row.api}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-700 dark:text-slate-200">{row.chat}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-700 dark:text-slate-200">{row.agent}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ── Section 4: SDK Downloads ── */}
          <section>
            <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-1 flex items-center gap-2">
              <Package size={20} className="text-violet-500" />
              SDK Downloads
            </h2>
            <p className="text-slate-500 dark:text-slate-400 text-sm mb-5">
              Official SDKs are coming soon. For now, use the REST API directly with any HTTP client.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-slate-950 rounded-2xl border border-slate-800 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-6 h-6 bg-blue-500 rounded flex items-center justify-center text-white text-[10px] font-bold">Py</span>
                  <span className="font-semibold text-slate-100">Python SDK</span>
                  <span className="ml-auto text-xs text-slate-500 font-mono">coming soon</span>
                </div>
                <code className="text-xs font-mono text-emerald-400">pip install synapse-sdk</code>
              </div>
              <div className="bg-slate-950 rounded-2xl border border-slate-800 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-6 h-6 bg-amber-500 rounded flex items-center justify-center text-white text-[10px] font-bold">TS</span>
                  <span className="font-semibold text-slate-100">TypeScript SDK</span>
                  <span className="ml-auto text-xs text-slate-500 font-mono">coming soon</span>
                </div>
                <code className="text-xs font-mono text-emerald-400">npm install @synapse/sdk</code>
              </div>
            </div>
          </section>

          {/* ── Section 5: Links ── */}
          <section className="flex flex-wrap gap-4">
            {[
              { href: '/settings', label: '🔑 Manage API Keys', desc: 'Create, view, and revoke your keys' },
              { href: `${BASE_URL}/api/schema/swagger-ui/`, label: '📋 Swagger UI', desc: 'Interactive API explorer', external: true },
              { href: `${BASE_URL}/api/schema/redoc/`, label: '📖 ReDoc Reference', desc: 'Full API documentation', external: true },
              { href: '/billing', label: '⬆️ Upgrade Plan', desc: 'Increase your rate limits' },
            ].map(link => (
              link.external ? (
                <a key={link.href} href={link.href} target="_blank" rel="noopener noreferrer"
                  className="flex-1 min-w-48 flex items-start gap-3 p-4 bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl hover:shadow-md hover:border-indigo-200 dark:hover:border-indigo-700/40 transition-all">
                  <div className="flex-1">
                    <div className="font-semibold text-sm text-slate-800 dark:text-slate-100 flex items-center gap-1">
                      {link.label} <ExternalLink size={11} className="text-slate-400" />
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">{link.desc}</div>
                  </div>
                </a>
              ) : (
                <Link key={link.href} href={link.href}
                  className="flex-1 min-w-48 flex items-start gap-3 p-4 bg-white dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/60 rounded-xl hover:shadow-md hover:border-indigo-200 dark:hover:border-indigo-700/40 transition-all">
                  <div>
                    <div className="font-semibold text-sm text-slate-800 dark:text-slate-100">{link.label}</div>
                    <div className="text-xs text-slate-400 mt-0.5">{link.desc}</div>
                  </div>
                </Link>
              )
            ))}
          </section>

        </div>
      </div>
    </div>
  );
}
