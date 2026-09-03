# Detasawy — Backend

Minimal Express API for Detasawy, under construction.

| Endpoint      | Response                                                  |
| ------------- | --------------------------------------------------------- |
| `GET /`       | `{"service":"detasawy-backend","status":"under construction"}` |
| `GET /health` | `{"service":"detasawy-backend","status":"ok","uptime":…}` |
| anything else | JSON 404                                                  |

## Structure

- `app.js` — the Express app (routes live here)
- `server.js` — local development server (`npm start`)
- `api/index.js` — Vercel serverless entry; `vercel.json` rewrites every path to it, so routes keep their public paths (`/`, `/health`, …)

## Run locally

```
npm install
npm start
```

Serves on `http://localhost:3001` (or whatever `PORT` is set to).

## Deploy on Vercel

1. [vercel.com/new](https://vercel.com/new) → import this repo.
2. The defaults work — Vercel detects `api/index.js` as a Node serverless function and installs dependencies from `package.json`.
3. Deploy.
