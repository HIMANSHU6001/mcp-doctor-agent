# MCP Doctor Agent

A full-stack doctor appointment assistant demonstrating strict MCP client-server tool orchestration with dynamic tool discovery.

## Stack

- Frontend: React + Vite
- Backend API: FastAPI
- MCP Server: FastMCP (SSE transport)
- Database: PostgreSQL + SQLAlchemy async
- LLM: OpenAI tool-calling
- External services:
  - Google Calendar (service account)
  - Resend email (patient confirmations)
  - Slack webhook (doctor report notifications)

## Architecture

1. Frontend sends chat prompt to FastAPI `/api/chat`.
2. FastAPI discovers tools at runtime from MCP server using `tools/list`.
3. LLM decides tool calls (`tool_choice=auto`).
4. FastAPI executes all tools through MCP `tools/call`.
5. MCP tools perform DB queries/mutations and integrations (Calendar, email, Slack).
6. FastAPI returns final assistant response to frontend.

## MCP Compliance Notes

- Tool execution is routed via MCP client-server protocol.
- Tool schemas are discovered dynamically from MCP server (no hardcoded tool schemas in API backend).
- Tool orchestration is LLM-driven via tool calls.
- Client/API server/MCP server/tool logic are separated into dedicated modules.

## Implemented Scenarios

### Scenario 1: Patient appointment scheduling

- Check availability via `get_doctor_availability_tool`.
- Book slot via `book_appointment_tool`.
- On successful booking:
  - appointment is written to PostgreSQL,
  - Google Calendar event is created,
  - patient confirmation email is sent.

### Scenario 2: Doctor summary and notification

- Doctor stats via `get_daily_stats`.
- Non-email notification via `send_doctor_report_notification` (Slack webhook).
- Trigger methods:
  - natural language prompts in chat,
  - dashboard button (frontend) calling `/api/doctor/report-notify`.

## Environment Setup

Copy `.env.example` to `.env` and configure at minimum:

- `OPENAI_API_KEY`
- `DATABASE_URL`
- `MCP_SERVER_URL`
- `GOOGLE_CLIENT_ID`
- `RESEND_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON`
- `GOOGLE_CALENDAR_ID` or `GOOGLE_CALENDAR_MAP_JSON`
- `SLACK_WEBHOOK_URL`

## Run (Docker)

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost`
- API: `http://localhost:8000`
- MCP server (SSE): `http://localhost:8001/sse`
- Postgres: `localhost:5432`

## Sample Prompts

Patient:

- "I want to check Dr. Ahuja's availability for Friday afternoon."
- "Book the 3 PM slot for me."

Doctor:

- "How many patients visited yesterday?"
- "Generate my daily report and notify me."

## API Summary

- `POST /api/auth/google`
- `POST /api/chat`
- `POST /api/doctor/report-notify`
