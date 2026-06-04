/**
 * TASK-606-2: Synapse Content Script
 *
 * Injected into supported pages (ArXiv, GitHub, HN, blog posts).
 * Adds a floating "Save to Synapse" button.
 */

(function () {
  'use strict';

  // Only inject once
  if (document.getElementById('synapse-save-btn')) return;

  // ── Create floating save button ─────────────────────────────────────────────

  const btn = document.createElement('button');
  btn.id = 'synapse-save-btn';
  btn.setAttribute('aria-label', 'Save to Synapse');
  btn.innerHTML = `
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
    </svg>
    <span id="synapse-btn-label">Save</span>
  `;

  // Position bottom-right
  Object.assign(btn.style, {
    position:        'fixed',
    bottom:          '24px',
    right:           '24px',
    zIndex:          '2147483647',
    display:         'flex',
    alignItems:      'center',
    gap:             '6px',
    padding:         '10px 16px',
    background:      'linear-gradient(135deg, #6366f1, #8b5cf6)',
    color:           '#fff',
    border:          'none',
    borderRadius:    '50px',
    fontSize:        '13px',
    fontWeight:      '600',
    fontFamily:      'system-ui, sans-serif',
    cursor:          'pointer',
    boxShadow:       '0 4px 20px rgba(99,102,241,0.5)',
    transition:      'all 0.2s ease',
    userSelect:      'none',
    backdropFilter:  'blur(8px)',
  });

  btn.addEventListener('mouseenter', () => { btn.style.transform = 'scale(1.05)'; });
  btn.addEventListener('mouseleave', () => { btn.style.transform = 'scale(1)'; });

  // ── Collect page metadata ────────────────────────────────────────────────────

  function getPageMeta() {
    const url   = window.location.href;
    const title = document.title || url;

    // Get selected text or first meaningful paragraph
    const selected = window.getSelection()?.toString().trim() || '';
    const desc =
      document.querySelector('meta[name="description"]')?.content ||
      document.querySelector('meta[property="og:description"]')?.content ||
      document.querySelector('article p')?.textContent?.slice(0, 500) ||
      '';

    return { url, title, selected_text: selected, description: desc };
  }

  // ── Click handler ─────────────────────────────────────────────────────────────

  btn.addEventListener('click', async () => {
    const label = document.getElementById('synapse-btn-label');
    if (!label) return;

    btn.disabled = true;
    label.textContent = 'Saving…';
    btn.style.opacity = '0.8';

    const meta = getPageMeta();

    try {
      const resp = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(
          { type: 'SAVE_PAGE', payload: { url: meta.url, title: meta.title, tags: [] } },
          (response) => {
            if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message));
            else resolve(response);
          }
        );
      });

      if (resp?.success) {
        label.textContent = 'Saved ✓';
        btn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
        setTimeout(() => {
          label.textContent = 'Save';
          btn.style.background = 'linear-gradient(135deg, #6366f1, #8b5cf6)';
          btn.disabled = false;
          btn.style.opacity = '1';
        }, 2500);
      } else {
        throw new Error(resp?.error || 'Save failed');
      }
    } catch (err) {
      label.textContent = err.message?.includes('API key') ? 'Set API key' : 'Error';
      btn.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)';
      btn.disabled = false;
      btn.style.opacity = '1';
      setTimeout(() => {
        label.textContent = 'Save';
        btn.style.background = 'linear-gradient(135deg, #6366f1, #8b5cf6)';
      }, 3000);
    }
  });

  document.body.appendChild(btn);

  // ── Hide button when typing in inputs ─────────────────────────────────────────

  document.addEventListener('focusin', (e) => {
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target?.tagName)) {
      btn.style.opacity = '0';
      btn.style.pointerEvents = 'none';
    }
  });
  document.addEventListener('focusout', () => {
    btn.style.opacity = '1';
    btn.style.pointerEvents = 'auto';
  });
})();
