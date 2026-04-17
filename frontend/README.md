# MCP Doctor Agent Frontend

React + Vite frontend for the MCP Doctor Agent.

## Features

- Role-based entry flow (patient or doctor)
- Optional Google sign-in (enabled when `VITE_GOOGLE_CLIENT_ID` is set)
- Chat UI connected to FastAPI backend endpoints
- Doctor Slack connect button and daily report action
- Toast feedback for login/logout, Slack connect, and report outcomes
- Role persistence across reload via local storage

## Prerequisites

- Node.js 18+
- Backend API running on `http://localhost:8000`

## Environment

Create `frontend/.env`:

```bash
VITE_GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
VITE_API_BASE_URL=http://localhost:8000
VITE_SLACK_CLIENT_ID=YOUR_SLACK_CLIENT_ID
```

Notes:

- If `VITE_GOOGLE_CLIENT_ID` is not set, Google sign-in is disabled and the UI shows setup guidance.
- Chat API uses `VITE_API_BASE_URL` with fallback `http://localhost:8000`.
- Slack OAuth URL generation uses `VITE_SLACK_CLIENT_ID`.

## Run Locally

```bash
npm install
npm run dev
```

Default app URL: `http://localhost:5173`

When running through root Docker Compose, the frontend is served on `http://localhost:3000`.

## Build

```bash
npm run build
npm run preview
```
