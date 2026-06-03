# Synapse Browser Extension

**TASK-606** — Chrome & Firefox extension for the Synapse AI Research Assistant.

## Features

| Feature | Description |
|---|---|
| 📚 **Save to Synapse** | Floating button on ArXiv, GitHub, HN, Medium etc. — one click saves the page to your knowledge base |
| 🧠 **Explain with AI** | Right-click any selected text → "Explain with Synapse AI" → RAG-powered explanation in popup |
| 🔍 **Quick Search** | Type in popup → instant search across all your articles, papers, and repos |
| ☀️ **Daily Briefing** | Popup shows today's AI-generated briefing on open |
| 🔗 **Context Menu** | "Save to Synapse" right-click option on any page or link |

## Installation (Development)

### Chrome / Edge
1. Open `chrome://extensions/`
2. Enable **Developer Mode** (top right toggle)
3. Click **Load unpacked** → select this `browser-extension/` folder
4. Click the Synapse icon → ⚙️ Settings → enter your API key

### Firefox
1. Open `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on** → select `manifest.json`
3. Click the Synapse icon → ⚙️ → enter your API key

> **Note:** Firefox uses Manifest V3 compatible WebExtensions API.
> The same manifest works for both browsers.

## Configuration

1. Get your API key from [app.synapse.app/settings](https://app.synapse.app/settings) → **API Keys** tab
2. Click the extension icon → ⚙️ Settings gear
3. Paste your `sk-syn-...` API key and click Save

## Files

| File | Purpose |
|---|---|
| `manifest.json` | Extension manifest (Manifest V3, Chrome + Firefox compatible) |
| `background.js` | Service worker — context menus, API calls, message router |
| `content.js` | Page injection — floating Save button on supported sites |
| `content.css` | Minimal styles for injected UI |
| `popup.html` | Extension popup layout |
| `popup.js` | Popup logic — briefing, search, save page |
| `options.html` | Settings page layout |
| `options.js` | Settings page logic — API key storage |

## Supported Pages (Content Script)

- arxiv.org
- github.com
- news.ycombinator.com
- reddit.com
- medium.com
- dev.to
- hackernoon.com
- towardsdatascience.com

## API Endpoints Used

| Action | Endpoint |
|---|---|
| Save page | `POST /api/v1/content/save/` |
| AI explanation | `POST /api/v1/ai/query/` |
| Quick search | `GET /api/v1/content/articles/?q=...` |
| Daily briefing | `GET /api/v1/briefing/today/` |

## Publishing

### Chrome Web Store
1. Zip the `browser-extension/` directory
2. Upload at [chrome.google.com/webstore/devconsole](https://chrome.google.com/webstore/devconsole)

### Firefox Add-ons (AMO)
1. Zip the directory
2. Submit at [addons.mozilla.org/developers](https://addons.mozilla.org/developers/)
