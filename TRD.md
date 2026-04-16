# Technical Requirements and Design (TRD)

Project: MCP Doctor Agent  
Author: Himanshu Kaushik  
Document status: Codebase-aligned snapshot  
Date: 2026-04-15

## 1. Purpose
This document describes the technical design implemented in this repository for a doctor appointment assistant that uses an LLM with MCP-based tool orchestration.

This TRD is intentionally aligned to the current codebase only. It does not assume any infrastructure configuration that is not present in source control.

## 2. Scope
In scope:
- Patient-side availability lookup and appointment booking through MCP tools.
- Doctor-side daily summary generation and non-email notification via Slack.
- Multi-turn chat continuity using session state.
- React frontend, FastAPI orchestration layer, FastMCP tool server, PostgreSQL persistence.

Out of scope:
- Direct Google Calendar write/sync integration.
- Production reverse-proxy specifics (Nginx tuning) not represented in this repository.

## 3. Functional Requirements

### 3.1 Patient flow
- User can ask for doctor availability in natural language.
- LLM can invoke MCP tools to fetch doctor list and availability.
- LLM can invoke MCP tool to book a selected slot.
- On successful booking, patient confirmation email and doctor notification email are attempted.
- If email delivery fails, booking remains confirmed and response still returns explicit delivery status.

### 3.2 Doctor flow
- User can request daily operational stats in natural language.
- LLM can invoke MCP tools to compute appointment count and fever mentions.
- LLM can invoke MCP tool to send summary via Slack webhook (non-email channel).
- Doctor report can also be triggered from a frontend action button that routes through the same chat orchestration.

### 3.3 Multi-turn continuity
- System keeps per-session message history and role context in memory.
- Follow-up prompts can continue prior intent without full restatement.

## 4. Non-Functional Requirements
- MCP compliance for discovery and tool execution.
- Async I/O for API and DB paths.
- Clear separation between frontend, API orchestration, MCP tool server, and data layer.
- Environment-variable based secret/configuration management.

## 5. Architecture Overview

## 5.1 Components
- Frontend: React + Vite UI.
- API server: FastAPI; receives chat/auth requests, calls LLM, handles MCP tool loop.
- MCP client: SSE client used by API for dynamic `tools/list` and `tools/call`.
- MCP server: FastMCP host for tools, prompts, and resources.
- Database: PostgreSQL accessed through SQLAlchemy async + asyncpg.
- Integrations: Resend (email), Slack incoming webhook (doctor report).

## 5.2 Runtime flow
1. Frontend sends prompt to API endpoint.
2. API refreshes MCP tools dynamically from MCP server.
3. API sends messages + dynamic tool schemas to LLM with auto tool choice.
4. LLM issues tool calls as needed.
5. API executes tools through MCP client-server protocol.
6. MCP tool functions perform DB/integration operations and return structured text/JSON.
7. API returns assistant response and tool outcomes to frontend.

## 6. MCP Design Compliance (Implementation Mapping)
- Dynamic discovery: MCP client calls `list_tools` and converts input schema to LLM function schema at runtime.
- Tool execution path: API executes requested tools only through MCP `call_tool`.
- LLM-driven orchestration: API chat loop uses model tool-calling with auto tool selection and iterative tool turn handling.
- Surface separation: MCP server defines prompts, resources, and tools independently of API route handlers.

## 7. Data Model and Persistence

### 7.1 Entities
- Doctor:
  - id, email (unique), name
- Appointment:
  - id, doctor_id, patient_name, symptoms, appointment_date, status

### 7.2 Booking rules enforced server-side
- Booking datetime must be timezone-naive (local time expected).
- Booking datetime must be on the hour (minute/second/microsecond = 0).
- Booking hour must be within 09:00 to 17:00 inclusive.
- Exact-slot conflict check prevents double booking.

### 7.3 Daily stats
- Counts scheduled appointments for a given date.
- Computes fever mentions from symptoms/patient text content.

## 8. API Surfaces
- `POST /api/auth/google`:
  - Verifies Google ID token and returns profile.
  - If role is doctor, ensures doctor profile exists in DB.
- `POST /api/chat`:
  - Main LLM + MCP orchestration endpoint for patient/doctor prompts.
- `POST /api/doctor/report-notify`:
  - Convenience endpoint to trigger report generation + Slack notification through doctor role flow.

## 9. Frontend Behavior
- Role-based entry (patient/doctor).
- Google sign-in optional (guarded by `VITE_GOOGLE_CLIENT_ID`).
- Chat interface for both roles.
- Doctor-only daily report action.
- Role and session persistence in local storage:
  - role key: `doctor-assistant-role`
  - session key: `doctor-assistant-session-id`

## 10. Deployment Topology in Repository
Docker Compose services:
- `db` (PostgreSQL)
- `mcp-server` (FastMCP tool server)
- `api` (FastAPI orchestration)
- `frontend` (Nginx static hosting for built frontend)

Published host ports in current compose file:
- DB: 5432
- MCP server: 8001
- API: 8000
- Frontend: 3000

## 11. Security and Reliability Notes
- Secrets are loaded from environment variables.
- Google auth tokens are verified server-side against configured audience.
- Tool call failures are captured and surfaced in structured outcomes.
- Email provider errors are normalized into actionable messages.

Known risk in current code:
- API CORS is configured with wildcard origins, suitable for development but not ideal for strict production hardening.

## 12. Limitations and Explicit Deferrals
- Google Calendar integration is intentionally deferred.
  - Reason: sensitive/restricted OAuth scope compliance overhead and policy verification requirements.
  - Current strategy: DB remains source of truth for appointments; notifications are sent via email/Slack.
- Session memory is in-process (not durable); restarting API clears chat history.
- Automated tests are minimal in current repository state.

## 13. Future Enhancements
- Add durable conversation memory (Redis or DB-backed).
- Add comprehensive backend/frontend test suites for MCP flows.
- Align all frontend API calls to a single env-driven API base.
- Restrict DB port exposure when running in production network topology.
- Add optional calendar sync adapter after OAuth policy and verification requirements are met.

## 14. Acceptance Checklist
- MCP tools are discovered dynamically at runtime.
- LLM tool orchestration executes through MCP protocol only.
- Patient booking and doctor reporting scenarios are functional end-to-end.
- Booking slot constraints are enforced server-side.
- Deferred Google Calendar integration is explicitly documented.
