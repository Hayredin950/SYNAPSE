/**
 * TASK-606-4: Synapse Popup Dashboard
 *
 * Shows:
 *  1. Today's briefing (loaded on open)
 *  2. AI explanation if triggered from context menu
 *  3. Quick search: type → top 3 results from Synapse
 *  4. Save current page button
 */

const $ = (id) => document.getElementById(id);
const contentArea = $('content-area');

const APP_URL = 'https://app.synapse.app'; // override in options

// ── Render helpers ────────────────────────────────────────────────────────────

function renderBriefing(briefing) {
  const paragraphs = (briefing.content || '').split(/\n+/).filter(Boolean);
  const preview    = paragraphs[0] || 'No briefing today.';
  return `
    <div class="briefing-card">
      <div class="briefing-label">☀️ Today's Brief</div>
      <div class="briefing-text">${escapeHtml(preview)}</div>
    </div>
  `;
}

function renderResults(results) {
  if (!results || results.length === 0) {
    return '<div class="empty">No results found.</div>';
  }
  return results.slice(0, 5).map(r => `
    <div class="result-item">
      <div class="result-icon">${r.type === 'paper' ? '📄' : r.type === 'repository' ? '⭐' : '📰'}</div>
      <div>
        <div class="result-title">${escapeHtml(r.title || r.full_name || 'Untitled')}</div>
        <div class="result-meta">${r.type || 'article'}</div>
      </div>
    </div>
  `).join('');
}

function renderExplanation(question, answer) {
  return `
    <div class="explanation-card">
      <div class="explanation-q">Q: ${escapeHtml(question.slice(0, 100))}${question.length > 100 ? '…' : ''}</div>
      <div class="explanation-a">${escapeHtml(answer)}</div>
    </div>
  `;
}

function renderError(msg) {
  return `<div class="error">⚠️ ${escapeHtml(msg)}</div>`;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function sendMsg(type, payload) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type, payload }, (resp) => {
      if (chrome.runtime.lastError) return reject(new Error(chrome.runtime.lastError.message));
      if (resp?.success) resolve(resp.data);
      else reject(new Error(resp?.error || 'Unknown error'));
    });
  });
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  // Check for pending AI explanation from context menu
  const session = await chrome.storage.session.get('lastExplanation');
  if (session.lastExplanation) {
    const { question, answer } = session.lastExplanation;
    contentArea.innerHTML = renderExplanation(question, answer);
    await chrome.storage.session.remove('lastExplanation');
    return;
  }

  // Load today's briefing
  try {
    const data = await sendMsg('GET_BRIEFING', {});
    contentArea.innerHTML = renderBriefing(data?.data ?? data ?? {});
  } catch (err) {
    if (err.message?.includes('API key')) {
      contentArea.innerHTML = renderError('API key not set. Click ⚙️ to add your key.');
    } else {
      contentArea.innerHTML = '<div class="empty">No briefing today. Check back after 06:30 UTC.</div>';
    }
  }
}

// ── Search ────────────────────────────────────────────────────────────────────

async function doSearch(q) {
  if (!q.trim()) return;
  contentArea.innerHTML = '<div class="loading">Searching…</div>';
  try {
    const data = await sendMsg('SEARCH', { q });
    const results = data?.data ?? data?.results ?? [];
    contentArea.innerHTML = results.length
      ? renderResults(results)
      : '<div class="empty">No results found.</div>';
  } catch (err) {
    // If it looks like a question, try AI query
    if (q.trim().endsWith('?') || q.split(' ').length > 3) {
      contentArea.innerHTML = '<div class="loading">Asking Synapse AI…</div>';
      try {
        const aiData = await sendMsg('AI_QUERY', { question: q });
        const answer = aiData?.data?.answer || 'No answer.';
        contentArea.innerHTML = renderExplanation(q, answer);
      } catch (aiErr) {
        contentArea.innerHTML = renderError(aiErr.message);
      }
    } else {
      contentArea.innerHTML = renderError(err.message);
    }
  }
}

$('search-btn').addEventListener('click', () => doSearch($('search-input').value));
$('search-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') doSearch($('search-input').value);
});

// ── Save current page ─────────────────────────────────────────────────────────

$('save-page-btn').addEventListener('click', async () => {
  const btn = $('save-page-btn');
  btn.disabled = true;
  btn.textContent = 'Saving…';

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    await sendMsg('SAVE_PAGE', { url: tab.url, title: tab.title, tags: [] });
    btn.textContent = '✓ Saved!';
    btn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
    setTimeout(() => {
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg> Save This Page`;
      btn.style.background = '';
      btn.disabled = false;
    }, 2500);
  } catch (err) {
    btn.textContent = 'Error — check API key';
    btn.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)';
    btn.disabled = false;
  }
});

// ── Settings & open app ───────────────────────────────────────────────────────

$('open-settings').addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});

$('open-app-link').addEventListener('click', (e) => {
  e.preventDefault();
  chrome.storage.sync.get('appUrl', ({ appUrl }) => {
    chrome.tabs.create({ url: appUrl || APP_URL });
  });
});

// ── Start ──────────────────────────────────────────────────────────────────────

init();
