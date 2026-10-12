# DocuMind AI: Frontend

React 19 + Vite 8 single-page app for DocuMind AI. It is built with plain CSS
(no UI framework), the Inter font and the blue-to-violet brand theme.

See the [main README](../README.md) for the full project documentation.

## Run

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # production build in dist/
npm run lint
```

The app talks to the backend at `http://127.0.0.1:8000/api/v1` by default.
To change it, create `frontend/.env`:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## Structure

| Path | Purpose |
|---|---|
| `src/main.jsx` | Mounts the app |
| `src/App.jsx` / `App.css` | Sign in, register, session restore, loading screen, logo and credits |
| `src/api.js` | API client: token storage, automatic refresh, every endpoint, formatters |
| `src/styles/Dashboard.css` | Workspace, chat and responsive (tablet + phone app shell) styles |
| `src/components/Dashboard.jsx` | Workspace shell: sidebar, top bar, pages, uploads, drag and drop |
| `src/components/Overview.jsx` | Dashboard home |
| `src/components/DocumentTable.jsx`, `DocumentDetails.jsx`, `DocumentBadges.jsx` | Documents page |
| `src/components/SearchView.jsx`, `SourceList.jsx` | AI search and sources |
| `src/components/ChatView.jsx`, `Markdown.jsx` | Chatbot and answer formatting |
| `src/components/AccountView.jsx` | Profile and password |
| `src/components/Select.jsx`, `Icons.jsx`, `Credits.jsx` | Shared UI pieces |

Every file is divided with `// ====` section titles so each part is easy to find.
