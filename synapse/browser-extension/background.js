/**
 * TASK-606-3: Synapse Browser Extension — Background Service Worker
 *
 * Responsibilities:
 *  - Register context menu items
 *  - Handle "Explain with Synapse AI" on text selection
 *  - Route messages from content.js / popup.js to the Synapse API
 */

const DEFAULT_API_BASE = 'https://api.synapse.app';

// ── Helpers ───────────────────────────────────────────────────────────────────

async function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(['apiKey', 'apiBase'], (result) => {
      resolve({
        apiKey:  result.apiKey  || '',
        apiBase: result.apiBase || DEFAULT_API_BASE,
      });
    });
  });
}

async function apiRequest(path, method = 'GET', body = null) {
  const { apiKey, apiBase } = await getConfig();
  if (!apiKey) throw new Error('No API key configured. Open Synapse extension settings.');

  const opts = {
    method,
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
  };
  if (body) opts.body = JSON.stringify(body);

  const resp = await fetch(`${apiBase}${path}`, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ── Context Menu Setup ────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  // TASK-606-3: "Explain with Synapse AI" context menu
  chrome.contextMenus.create({
    id:       'synapse-explain',
    title:    '🧠 Explain with Synapse AI',
    contexts: ['selection'],
  });

  // "Save to Synapse" context menu
  chrome.contextMenus.create({
    id:       'synapse-save',
    title:    '📚 Save to Synapse',
    contexts: ['page', 'link'],
  });
});

// ── Context Menu Click Handler ────────────────────────────────────────────────

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'synapse-explain') {
    const selectedText = info.selectionText?.trim();
    if (!selectedText) return;

    try {
      const result = await apiRequest('/api/v1/ai/query/', 'POST', {
        question: selectedText,
      });

      const answer = result?.data?.answer || 'No explanation available.';

      // Open popup with the answer stored in session storage
      await chrome.storage.session.set({ lastExplanation: { question: selectedText, answer } });

      // Open the popup programmatically
      chrome.action.openPopup().catch(() => {
        // Fallback: show a notification
        chrome.notifications.create({
          type:    'basic',
          iconUrl: 'icons/icon-48.png',
          title:   'Synapse AI Explanation',
          message: answer.slice(0, 200) + (answer.length > 200 ? '…' : ''),
        });
      });

    } catch (err) {
      chrome.notifications.create({
        type:    'basic',
        iconUrl: 'icons/icon-48.png',
        title:   'Synapse Error',
        message: err.message || 'Failed to get AI explanation.',
      });
    }
  }

  if (info.menuItemId === 'synapse-save') {
    const url   = info.linkUrl || tab?.url || '';
    const title = tab?.title  || url;
    try {
      await apiRequest('/api/v1/content/save/', 'POST', { url, title });
      chrome.notifications.create({
        type:    'basic',
        iconUrl: 'icons/icon-48.png',
        title:   'Saved to Synapse ✓',
        message: `"${title.slice(0, 60)}" added to your knowledge base.`,
      });
    } catch (err) {
      chrome.notifications.create({
        type:    'basic',
        iconUrl: 'icons/icon-48.png',
        title:   'Save Failed',
        message: err.message || 'Could not save to Synapse.',
      });
    }
  }
});

// ── Message Router (from content.js / popup.js) ───────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { type, payload } = message;

  if (type === 'SAVE_PAGE') {
    apiRequest('/api/v1/content/save/', 'POST', payload)
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // keep message channel open for async response
  }

  if (type === 'AI_QUERY') {
    apiRequest('/api/v1/ai/query/', 'POST', { question: payload.question })
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (type === 'SEARCH') {
    apiRequest(`/api/v1/content/articles/?q=${encodeURIComponent(payload.q)}&limit=5`)
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (type === 'GET_BRIEFING') {
    apiRequest('/api/v1/briefing/today/')
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});
