/**
 * Synapse Extension Options Page
 */

const $ = (id) => document.getElementById(id);

// ── Load saved settings ──────────────────────────────────────────────────────

chrome.storage.sync.get(['apiKey', 'apiBase', 'appUrl'], (result) => {
  if (result.apiKey)  $('api-key').value  = result.apiKey;
  if (result.apiBase) $('api-base').value = result.apiBase;
  if (result.appUrl)  $('app-url').value  = result.appUrl;
});

// ── Save ──────────────────────────────────────────────────────────────────────

$('save-btn').addEventListener('click', () => {
  const apiKey  = $('api-key').value.trim();
  const apiBase = $('api-base').value.trim() || 'https://api.synapse.app';
  const appUrl  = $('app-url').value.trim()  || 'https://app.synapse.app';

  if (!apiKey) {
    showStatus('Please enter your API key.', 'error');
    return;
  }
  if (!apiKey.startsWith('sk-syn-')) {
    showStatus('Invalid key format. Keys start with sk-syn-…', 'error');
    return;
  }

  chrome.storage.sync.set({ apiKey, apiBase, appUrl }, () => {
    showStatus('Settings saved ✓', 'success');
  });
});

function showStatus(msg, type) {
  const el = $('status-msg');
  el.textContent = msg;
  el.className   = `status ${type}`;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 3000);
}
