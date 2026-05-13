'use client';

import React, { useEffect, useRef, useState } from 'react';

interface MermaidBlockProps {
  code: string;
}

/**
 * Renders a Mermaid diagram by dynamically importing the mermaid library
 * and calling mermaid.render() on the client side only.
 */
export function MermaidBlock({ code }: MermaidBlockProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [svg, setSvg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function renderDiagram() {
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          themeVariables: {
            primaryColor: '#6366f1',
            primaryTextColor: '#e2e8f0',
            primaryBorderColor: '#4f46e5',
            lineColor: '#94a3b8',
            secondaryColor: '#1e293b',
            tertiaryColor: '#0f172a',
            background: '#1e293b',
            mainBkg: '#1e293b',
            nodeBorder: '#4f46e5',
          },
        });
        const id = `mermaid-${Math.random().toString(36).slice(2)}`;
        const { svg: rendered } = await mermaid.render(id, code);
        if (!cancelled) setSvg(rendered);
      } catch (e: any) {
        if (!cancelled) setError(e?.message ?? 'Failed to render diagram');
      }
    }
    renderDiagram();
    return () => { cancelled = true; };
  }, [code]);

  if (error) {
    return (
      <div className="my-3 rounded-lg border border-red-800 bg-red-950/40 p-4">
        <p className="text-xs text-red-400 font-mono mb-2">Mermaid render error:</p>
        <pre className="text-xs text-red-300 overflow-x-auto whitespace-pre-wrap">{error}</pre>
        <pre className="mt-2 text-xs text-slate-400 overflow-x-auto">{code}</pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="my-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-900 p-4 flex items-center gap-2">
        <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-slate-400">Rendering diagram…</span>
      </div>
    );
  }

  return (
    <div
      ref={ref}
      className="my-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100 dark:bg-slate-900 p-4 overflow-x-auto flex justify-center"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
