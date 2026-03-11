# Web App

`apps/web` is now a small Next.js app-router frontend for the first read-only materials workbench surface.

Current routes:

- `/`: overview workbench
- `/campaigns`: read-only campaign registry
- `/campaigns/[campaignId]`: run twin view for a campaign
- `/skills`: read-only skill catalog

## Why Next.js here

Yes, this frontend is better suited as a Next.js app than as static HTML files.

Reasons:

- server components can fetch the API with auth headers without moving tokens into browser state
- route-level data loading fits the workbench shape better than one large client script
- the app router gives a clean path toward richer read models, detail pages, and streaming sections
- this aligns with the intended evolution toward a real product surface rather than a demo shell

## Local run

Install dependencies:

```bash
npm install
```

Start the API:

```bash
uv run uvicorn autolab.api.main:app --reload
```

Start the web app:

```bash
npm run dev
```

Then open [http://127.0.0.1:3000](http://127.0.0.1:3000).

## Environment

The app uses these variables when present:

- `AUTOLAB_API_BASE_URL`
- `NEXT_PUBLIC_AUTOLAB_API_BASE_URL`
- `AUTOLAB_API_TOKEN`

Fallbacks for local development:

- base URL: `http://127.0.0.1:8000`
- token: `dev-token`

The interface architecture is documented in [docs/architecture/materials-workbench-ui.md](../../docs/architecture/materials-workbench-ui.md).
