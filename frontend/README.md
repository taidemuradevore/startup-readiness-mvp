# Startup Readiness Frontend

Next.js + TypeScript frontend for the `startup-readiness-mvp` backend API.

## Requirements Covered

- App Router
- Tailwind
- dashboard page showing decks
- deck detail page at `/decks/[deck_id]`
- shared API layer in `lib/api.ts`
- loading and error states
- backend base URL via `NEXT_PUBLIC_API_URL`

## Environment

Set the backend URL before running:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Run

```bash
npm run dev
```

## API Workflows Included

The home page includes forms for:

- `POST /api/decks/from-json`
- `POST /api/decks/ingest-from-json`
- `POST /api/decks/retrieve`
- `POST /api/decks/evaluate`
- `POST /api/decks/evaluate-upload`

The deck detail page fetches slides from:

- `GET /api/decks/:deck_id/slides`

The dashboard expects a deck list endpoint at:

- `GET /api/decks`

If the list/slides endpoints are unavailable, the UI falls back to small example deck data so the frontend remains navigable during backend development. The workflow endpoints do not use mock success responses.
