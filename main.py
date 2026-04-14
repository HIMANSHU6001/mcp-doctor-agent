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

from database import (
    book_appointment_db,
    get_daily_stats_db,
    get_doctor_availability,
    init_db,
)
from email_service import send_booking_confirmation

load_dotenv()

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


class GoogleAuthRequest(BaseModel):
    token: str = Field(..., min_length=1)


class GoogleAuthResponse(BaseModel):
    email: str
    name: str
    picture: str | None = None


def _build_system_prompt(
    role: Literal["patient", "doctor"],
    user_name: str | None,
    user_email: str | None,
) -> str:
    """Build the role-specific system prompt with user context."""
    current_date = datetime.now().strftime("%Y-%m-%d")
    resolved_name = user_name or "the user"
    resolved_email = user_email or "not provided"
    return (
        f"{SYSTEM_PROMPTS[role]}\n\n"
        f"You are talking to {resolved_name}. Their email is {resolved_email}.\n"
        f"IMPORTANT: Today's date is {current_date}. Use this to resolve relative dates like 'tomorrow' into YYYY-MM-DD format."
    )


@app.on_event("startup")
async def on_startup() -> None:
    """Ensure tables exist before handling requests."""
    await init_db()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
client: AsyncOpenAI | None = None
google_request = Request()
SESSION_MEMORY: Dict[str, List[Dict[str, str]]] = {}
SESSION_ROLES: Dict[str, Literal["patient", "doctor"]] = {}
MAX_SESSION_MESSAGES = 12

SYSTEM_PROMPTS: Dict[str, str] = {
    "patient": (
        "You are a healthcare appointment assistant helping a patient. "
        "Use tools when scheduling or availability information is needed. "
        "Be clear, practical, and concise."
    ),
    "doctor": (
        "You are a healthcare appointment assistant helping a doctor manage appointments. "
        "Use tools for schedule lookup and booking actions. "
        "Be precise and operationally focused. When the user asks for a daily report "
        "or daily stats, call get_daily_stats with today's date in YYYY-MM-DD format."
    ),
}

# Tool schemas mirror tools exposed in mcp_server.py.
TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_doctor_availability_tool",
            "description": (
                "Get available appointment times for a doctor on a specific date. "
                "Date must be in YYYY-MM-DD format."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Canonical doctor name, for example 'Dr. Ahuja'.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Target date in YYYY-MM-DD format.",
                    },
                },
                "required": ["doctor_name", "date"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment_tool",
            "description": (
                "Book an appointment for a doctor and patient at an exact datetime slot."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_name": {
                        "type": "string",
                        "description": "Canonical doctor name, for example 'Dr. Ahuja'.",
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Full patient name for the booking.",
                    },
                    "patient_email": {
                        "type": "string",
                        "format": "email",
                        "description": "Patient email address for the booking confirmation.",
                    },
                    "date_time": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Appointment timestamp in ISO-8601 format.",
                    },
                },
                "required": ["doctor_name", "patient_name", "patient_email", "date_time"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_daily_stats",
            "description": "Summarize today's appointment count and fever mentions for a doctor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Target date in YYYY-MM-DD format.",
                    },
                },
                "required": ["date"],
                "additionalProperties": False,
            },
        },
    },
]


async def _execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a known tool with real backend logic and normalized JSON output."""
    if tool_name == "get_doctor_availability_tool":
        doctor_name = str(args.get("doctor_name", ""))
        date = str(args.get("date", ""))
        result = await get_doctor_availability(doctor_name=doctor_name, date=date)
        return {
            "ok": True,
            "tool": tool_name,
            "result": result,
        }

    if tool_name == "book_appointment_tool":
        doctor_name = str(args.get("doctor_name", ""))
        patient_name = str(args.get("patient_name", ""))
        patient_email = str(args.get("patient_email", "")).strip()
        date_time_str = str(args.get("date_time", ""))

        if not patient_email:
            return {
                "ok": False,
                "tool": tool_name,
                "error": "patient_email is required for booking confirmations.",
            }

        try:
            date_time = datetime.fromisoformat(date_time_str.replace("Z", "+00:00"))
        except ValueError:
            return {
                "ok": False,
                "tool": tool_name,
                "error": "Invalid date_time format. Use ISO-8601 date-time.",
            }

        result = await book_appointment_db(
            doctor_name=doctor_name,
            patient_name=patient_name,
            date_time=date_time,
        )

        email_delivery = None
        if result.startswith("Appointment booked for"):
            email_delivery = await send_booking_confirmation(
                patient_email=patient_email,
                patient_name=patient_name,
                doctor_name=doctor_name,
                date_time=date_time.isoformat(),
            )

        return {
            "ok": True,
            "tool": tool_name,
            "result": result,
            "email_sent": email_delivery is not None,
            "email_response": str(email_delivery) if email_delivery is not None else None,
        }

    if tool_name == "get_daily_stats":
        return await get_daily_stats_db(
            str(args.get("date", datetime.now().date().isoformat()))
        )

    return {
        "ok": False,
        "tool": tool_name,
        "error": "Tool is not recognized by the backend dispatcher.",
    }


@app.post("/api/auth/google", response_model=GoogleAuthResponse)
async def google_auth_endpoint(payload: GoogleAuthRequest) -> GoogleAuthResponse:
    """Verify a Google OAuth token and return the user profile."""
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

    return GoogleAuthResponse(email=email, name=name, picture=picture)


def _get_openai_client() -> AsyncOpenAI:
    """Create and cache OpenAI client only when an API key is available."""
    global client

    if client is not None:
        return client

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in the .env file.")

    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url="https://models.inference.ai.azure.com"
    )
    return client


async def process_chat(
    prompt: str,
    role: Literal["patient", "doctor"],
    session_id: str,
    user_name: str | None = None,
    user_email: str | None = None,
) -> str:
    """Run chat completion loop until the model returns a final text answer."""
    openai_client = _get_openai_client()

    if session_id in SESSION_ROLES and SESSION_ROLES[session_id] != role:
        SESSION_MEMORY[session_id] = []

    SESSION_ROLES[session_id] = role
    history = SESSION_MEMORY.get(session_id, [])

    dynamic_system_prompt = _build_system_prompt(role=role, user_name=user_name, user_email=user_email)

    messages: List[Dict[str, Any]] = [{"role": "system", "content": dynamic_system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    max_turns = 8
    turn = 0

    while True:
        turn += 1
        if turn > max_turns:
            return "I could not finish the request after several tool calls. Please try again."

        completion = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
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
                print(f"Tool called: {tool_name}")

                try:
                    parsed_args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    parsed_args = {"_raw_arguments": tool_call.function.arguments}

                tool_result = await _execute_tool(tool_name=tool_name, args=parsed_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(tool_result),
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
        return final_text


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        session_id = payload.session_id or str(uuid.uuid4())
        response_text = await process_chat(
            prompt=payload.prompt,
            role=payload.role,
            session_id=session_id,
            user_name=payload.user_name,
            user_email=payload.user_email,
        )
        return ChatResponse(response=response_text, session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process chat: {exc}") from exc