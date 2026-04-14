from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from database import get_daily_stats_db

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


class ChatResponse(BaseModel):
    response: str


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client: AsyncOpenAI | None = None

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

# Hardcoded tool schemas mirror tools exposed in mcp_server.py.
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
                    "date_time": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Appointment timestamp in ISO-8601 format.",
                    },
                },
                "required": ["doctor_name", "patient_name", "date_time"],
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


def _fake_tool_json(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Return deterministic fake tool data for early integration testing."""
    if tool_name == "get_doctor_availability_tool":
        return {
            "status": "simulated",
            "tool": tool_name,
            "doctor_name": args.get("doctor_name", ""),
            "date": args.get("date", ""),
            "available_slots": ["09:00", "10:00", "11:00", "14:00"],
            "note": "Fake response. Wire to MCP server for live database data.",
        }

    if tool_name == "book_appointment_tool":
        return {
            "status": "simulated_success",
            "tool": tool_name,
            "doctor_name": args.get("doctor_name", ""),
            "patient_name": args.get("patient_name", ""),
            "date_time": args.get("date_time", ""),
            "note": "Fake response. No real booking has been persisted yet.",
        }

    return {
        "status": "unsupported_tool",
        "tool": tool_name,
        "note": "Tool is not recognized by the fake dispatcher.",
    }


def _get_openai_client() -> AsyncOpenAI:
    """Create and cache OpenAI client only when an API key is available."""
    global client

    if client is not None:
        return client

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in the .env file.")

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return client


async def process_chat(prompt: str, role: Literal["patient", "doctor"]) -> str:
    """Run chat completion loop until the model returns a final text answer."""
    openai_client = _get_openai_client()

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPTS[role]},
        {"role": "user", "content": prompt},
    ]

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

                if tool_name == "get_daily_stats":
                    fake_result = await get_daily_stats_db(
                        parsed_args.get("date", datetime.now().date().isoformat())
                    )
                else:
                    fake_result = _fake_tool_json(tool_name=tool_name, args=parsed_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(fake_result),
                    }
                )

            continue

        return message.content or "No response generated by the model."


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        response_text = await process_chat(prompt=payload.prompt, role=payload.role)
        return ChatResponse(response=response_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process chat: {exc}") from exc