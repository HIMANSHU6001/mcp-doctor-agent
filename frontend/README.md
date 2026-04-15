# MCP Doctor Agent Frontend

React + Vite frontend for the MCP Doctor Agent.

## Features

- Role-based entry flow (patient or doctor)
- Optional Google sign-in (enabled when `VITE_GOOGLE_CLIENT_ID` is set)
- Chat UI connected to FastAPI backend endpoints
- Doctor action button to trigger daily report notification

## Prerequisites

- Node.js 18+
- Backend API running on `http://localhost:8000`

## Environment

Create `frontend/.env`:

```bash
VITE_GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
```

Notes:

- If `VITE_GOOGLE_CLIENT_ID` is not set, Google sign-in is disabled and the UI shows setup guidance.
- Backend base URL is currently hardcoded to `http://localhost:8000` in the frontend source.

## Run Locally

```bash
npm install
npm run dev
```

Default app URL: `http://localhost:5173`

## Build

```bash
npm run build
npm run preview
```
