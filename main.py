from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from database import get_or_create_doctor_by_email, init_db
from mcp_client import MCPToolClient

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8001/sse")

openai_client: AsyncOpenAI | None = None
google_request = Request()
mcp_tool_client = MCPToolClient(server_url=MCP_SERVER_URL)

SESSION_MEMORY: Dict[str, List[Dict[str, str]]] = {}
SESSION_ROLES: Dict[str, Literal["patient", "doctor"]] = {}
MAX_SESSION_MESSAGES = 12

SYSTEM_PROMPTS: Dict[str, str] = {
    "patient": (
        "You are a healthcare appointment assistant helping a patient. "
        "Use tools when scheduling or availability information is needed. "
        "When booking, call book_appointment_tool with patient_email for confirmation. "
        "When asked which doctors are available, call list_doctors_tool. "
        "For booking outcomes, clearly report both booking status and email delivery status. "
        "Do not mention unsupported integrations. "
        "Be clear, practical, and concise."
    ),
    "doctor": (
        "You are a healthcare appointment assistant helping a doctor manage appointments. "
        "Use tools for schedule lookup and reporting actions. "
        "When asked for daily stats, call get_daily_stats. "
        "When asked to send or notify a report, call get_daily_stats first and then call send_doctor_report_notification. "
        "Be precise and operationally focused."
    ),
}

app = FastAPI(title="Doctor Assistant Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    role: Literal["patient", "doctor"]
    session_id: str | None = None
    user_name: str | None = None
    user_email: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_outcomes: List[Dict[str, Any]] = Field(default_factory=list)


class GoogleAuthRequest(BaseModel):
    token: str = Field(..., min_length=1)
    role: Literal["patient", "doctor"] = "patient"


class GoogleAuthResponse(BaseModel):
    email: str
    name: str
    picture: str | None = None


class DoctorReportRequest(BaseModel):
    doctor_name: str = Field(default="Doctor")
    doctor_email: str = Field(..., min_length=3)
    date: str | None = None


class DoctorReportResponse(BaseModel):
    report: str
    date: str
    sent: bool
    notification: Dict[str, Any] = Field(default_factory=dict)


def _build_system_prompt(
    role: Literal["patient", "doctor"],
    user_name: str | None,
    user_email: str | None,
) -> str:
    current_date = datetime.now().strftime("%Y-%m-%d")
    resolved_name = user_name or "the user"
    resolved_email = user_email or "not provided"

    return (
        f"{SYSTEM_PROMPTS[role]}\\n\\n"
        f"You are talking to {resolved_name}. Their email is {resolved_email}.\\n"
        f"Today's date is {current_date}. Resolve relative dates like 'tomorrow' into YYYY-MM-DD."
    )


def _parse_json_if_possible(raw_text: str) -> Any:
    try:
        return json.loads(raw_text)
    except Exception:
        # Try extracting just the first JSON object if multi-line
        lines = raw_text.strip().split('\n')
        for line in lines:
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
        return raw_text


def _find_tool_outcome(tool_outcomes: List[Dict[str, Any]], tool_name: str) -> Dict[str, Any] | None:
    for outcome in reversed(tool_outcomes):
        if outcome.get("tool") == tool_name:
            return outcome
    return None


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    await mcp_tool_client.connect()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await mcp_tool_client.close()


@app.post("/api/auth/google", response_model=GoogleAuthResponse)
async def google_auth_endpoint(payload: GoogleAuthRequest) -> GoogleAuthResponse:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID is missing. Set it in the .env file.")

    try:
        token_info = id_token.verify_oauth2_token(payload.token, google_request, audience=GOOGLE_CLIENT_ID)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}") from exc

    email = str(token_info.get("email", "")).strip()
    name = str(token_info.get("name", "")).strip()
    picture = token_info.get("picture")

    if not email or not name:
        raise HTTPException(status_code=401, detail="Google token did not include profile information.")

    if payload.role == "doctor":
        sync_result = await get_or_create_doctor_by_email(doctor_email=email, doctor_name=name)
        if not sync_result.get("ok"):
            raise HTTPException(
                status_code=500,
                detail=sync_result.get("message", "Failed to sync doctor profile."),
            )

    return GoogleAuthResponse(email=email, name=name, picture=picture)


def _get_openai_client() -> AsyncOpenAI:
    global openai_client

    if openai_client is not None:
        return openai_client

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in the .env file.")

    openai_client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url="https://models.inference.ai.azure.com",
    )
    return openai_client


async def _get_discovered_openai_tools() -> List[Dict[str, Any]]:
    await mcp_tool_client.refresh_tools()
    tools = mcp_tool_client.get_openai_tools()
    if not tools:
        raise RuntimeError("MCP server returned no tools during discovery.")
    return tools


async def process_chat(
    prompt: str,
    role: Literal["patient", "doctor"],
    session_id: str,
    user_name: str | None = None,
    user_email: str | None = None,
) -> tuple[str, List[Dict[str, Any]]]:
    client = _get_openai_client()
    discovered_tools = await _get_discovered_openai_tools()

    if session_id in SESSION_ROLES and SESSION_ROLES[session_id] != role:
        SESSION_MEMORY[session_id] = []

    SESSION_ROLES[session_id] = role
    history = SESSION_MEMORY.get(session_id, [])

    dynamic_system_prompt = _build_system_prompt(role=role, user_name=user_name, user_email=user_email)

    messages: List[Dict[str, Any]] = [{"role": "system", "content": dynamic_system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    tool_outcomes: List[Dict[str, Any]] = []
    max_turns = 8
    turn = 0

    while True:
        turn += 1
        if turn > max_turns:
            return (
                "I could not finish the request after several tool calls. Please try again.",
                tool_outcomes,
            )

        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=discovered_tools,
            tool_choice="auto",
        )

        message = completion.choices[0].message
        tool_calls = message.tool_calls or []

        if tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in tool_calls
                    ],
                }
            )

            for tool_call in tool_calls:
                tool_name = tool_call.function.name

                try:
                    parsed_args = json.loads(tool_call.function.arguments or "{}")
                    if not isinstance(parsed_args, dict):
                        parsed_args = {"value": parsed_args}
                except json.JSONDecodeError:
                    parsed_args = {"_raw_arguments": tool_call.function.arguments}

                try:
                    tool_result_text = await mcp_tool_client.call_tool(
                        name=tool_name,
                        arguments=parsed_args,
                    )
                except Exception as exc:
                    tool_result_text = json.dumps(
                        {
                            "ok": False,
                            "tool": tool_name,
                            "message": f"MCP tool call failed: {exc}",
                        }
                    )

                parsed_result = _parse_json_if_possible(tool_result_text)
                tool_outcomes.append(
                    {
                        "tool": tool_name,
                        "arguments": parsed_args,
                        "result": parsed_result,
                    }
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": tool_result_text,
                    }
                )

            continue

        final_text = message.content or "No response generated by the model."
        updated_history = [
            *history,
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": final_text},
        ]
        SESSION_MEMORY[session_id] = updated_history[-MAX_SESSION_MESSAGES:]
        return final_text, tool_outcomes


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        session_id = payload.session_id or str(uuid.uuid4())
        response_text, tool_outcomes = await process_chat(
            prompt=payload.prompt,
            role=payload.role,
            session_id=session_id,
            user_name=payload.user_name,
            user_email=payload.user_email,
        )
        return ChatResponse(response=response_text, session_id=session_id, tool_outcomes=tool_outcomes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process chat: {exc}") from exc


@app.post("/api/doctor/report-notify", response_model=DoctorReportResponse)
async def doctor_report_notify_endpoint(payload: DoctorReportRequest) -> DoctorReportResponse:
    target_date = payload.date or datetime.now().strftime("%Y-%m-%d")

    prompt = (
        f"Generate my daily report for {target_date} and notify me on Slack. "
        f"I am {payload.doctor_name} and my email is {payload.doctor_email}."
    )

    try:
        response_text, tool_outcomes = await process_chat(
            prompt=prompt,
            role="doctor",
            session_id=f"doctor-report:{payload.doctor_email}",
            user_name=payload.doctor_name,
            user_email=payload.doctor_email,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MCP report notification failed: {exc}") from exc

    report_outcome = _find_tool_outcome(tool_outcomes, "send_doctor_report_notification")
    notification: Dict[str, Any] = {}
    sent = False
    report = response_text

    if report_outcome is not None:
        parsed_report = report_outcome.get("result")
        if isinstance(parsed_report, dict):
            notification_value = parsed_report.get("notification", {})
            if isinstance(notification_value, dict):
                notification = notification_value
            else:
                notification = {"raw": notification_value}

            report = str(
                parsed_report.get("report")
                or parsed_report.get("summary")
                or parsed_report.get("message")
                or response_text
            )
            sent = bool(notification.get("ok")) or bool(parsed_report.get("ok", False))

    return DoctorReportResponse(
        report=report,
        date=target_date,
        sent=sent,
        notification=notification,
    )
