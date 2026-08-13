# WageLens Frontend

Next.js app for registering voice/text complaints and viewing the dashboard.

## Setup

```bash
cd frontend
cp .env.example .env
npm install
```

## Environment

In `.env`:

- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8080` — browser API calls
- `BACKEND_URL=http://localhost:8080` — Next.js server-side `/backend` proxy rewrites

## Run

```bash
npm run dev
```

App: `http://localhost:3000`

Start the [backend](../backend/README.md) first.

Back to [project README](../README.md).
