# MCP Doctor Agent

A full-stack doctor appointment assistant demonstrating strict MCP client-server tool orchestration with dynamic tool discovery.

For architecture decisions and constraints aligned to this repository, see `TRD.md`.

## Stack

- Frontend: React + Vite
- Backend API: FastAPI
- MCP Server: FastMCP (SSE transport)
- Database: PostgreSQL + SQLAlchemy async
- LLM: OpenAI tool-calling
- External services:
  - Resend email (patient confirmations + doctor booking notifications)
  - Slack OAuth + Slack Web API DM (doctor report notifications)

## Architecture

1. Frontend sends chat prompt to FastAPI `/api/chat`.
2. FastAPI discovers tools at runtime from MCP server using `tools/list`.
3. LLM decides tool calls (`tool_choice=auto`).
4. FastAPI executes all tools through MCP `tools/call`.
5. MCP tools perform DB queries/mutations and integrations (email, Slack).
6. FastAPI returns final assistant response to frontend.

## MCP Compliance Notes

- Tool execution is routed via MCP client-server protocol.
- Tool schemas are discovered dynamically from MCP server (no hardcoded tool schemas in API backend).
- Tool orchestration is LLM-driven via tool calls.
- Client/API server/MCP server/tool logic are separated into dedicated modules.
- MCP prompt and resource surfaces are exposed at runtime alongside tools.

## Implemented Scenarios

### Scenario 1: Patient appointment scheduling

- List available doctors via `list_doctors_tool`.
- Check availability via `get_doctor_availability_tool`.
- Book slot via `book_appointment_tool`.
- Booking validation is enforced server-side (hourly slots only, 09:00-17:00 inclusive, timezone-naive input expected).
- On successful booking:
  - appointment is written to PostgreSQL,
  - patient confirmation email is sent,
  - doctor notification email is sent with patient and appointment details.

### Scenario 2: Doctor summary and notification

- Doctor stats via `get_daily_stats`.
- Email delivery via `send_doctor_report_notification` (always attempted).
- Slack DM delivery via `send_doctor_report_notification` when the doctor has connected Slack.
- Trigger methods:
  - natural language prompts in chat,
  - dashboard button that now routes through the same chat orchestration path.

## Environment Setup

Copy `.env.example` to `.env` and configure at minimum:

- `OPENAI_API_KEY`
- `DATABASE_URL`
- `MCP_SERVER_URL`
- `GOOGLE_CLIENT_ID`
- `RESEND_API_KEY`
- `RESEND_FROM_EMAIL` (required for reliable delivery in production)
- `SLACK_CLIENT_ID`
- `SLACK_CLIENT_SECRET`
- `FRONTEND_BASE_URL`
- `VITE_SLACK_CLIENT_ID` (frontend)

Calendar integration is intentionally deferred in this submission due to Google OAuth sensitive scope policy and verification overhead.

Recommended local `DATABASE_URL` in Docker:

- `postgresql://postgres:supersecret@db:5432/appointment_db`

Email notes:

- Booking attempts two email sends independently: one to patient, one to doctor.
- If booking succeeds but email delivery fails, booking remains confirmed and API response includes explicit email status fields.

## Run (Docker)

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000`
- MCP server (SSE): `http://localhost:8001/sse`
- Postgres: `localhost:5432`

## Sample Prompts

Patient:

- "I want to check Dr. Ahuja's availability for Friday afternoon."
- "Book the 3 PM slot for me."

Doctor:

- "How many patients visited yesterday?"
- "Generate my daily report and send it to my email and Slack if connected."

Available MCP prompt/resource entries:

- `patient_booking_prompt`
- `doctor_report_prompt`
- `resource://doctor-assistant/guide`
- `resource://doctor-assistant/doctors/{doctor_name}`

## API Summary

- `POST /api/auth/google`
- `GET /api/auth/slack/callback`
- `POST /api/chat`
- `POST /api/doctor/report-notify`

## Known Limitations

- Session memory is in-process and resets when the API service restarts.
- API startup intentionally performs a destructive schema reset (`doctors` and `appointments`) for this rollout.
