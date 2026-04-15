from __future__ import annotations

import asyncio
import json
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from database import (
    book_appointment_db as book_appointment_db_helper,
    get_daily_stats_db,
    get_doctor_availability as get_doctor_availability_helper,
    init_db,
)
from email_service import send_booking_confirmation
from notification_service import send_doctor_report_to_slack

mcp = FastMCP("DoctorAssistant", host="0.0.0.0", port=8001)
_db_init_lock = asyncio.Lock()
_db_initialized = False


def _as_json(payload: dict) -> str:
    return json.dumps(payload, default=str)


async def _ensure_db_initialized() -> None:
    """Initialize database objects once inside the active server event loop."""
    global _db_initialized
    if _db_initialized:
        return

    async with _db_init_lock:
        if _db_initialized:
            return
        await init_db()
        _db_initialized = True


@mcp.tool()
async def get_doctor_availability_tool(doctor_name: str, date: str) -> str:
    """Get doctor availability for a date and return normalized JSON text."""
    await _ensure_db_initialized()
    availability = await get_doctor_availability_helper(doctor_name=doctor_name, date=date)
    success = availability.startswith("Available slots for")
    return _as_json(
        {
            "ok": success,
            "tool": "get_doctor_availability_tool",
            "doctor_name": doctor_name,
            "date": date,
            "message": availability,
        }
    )


@mcp.tool()
async def book_appointment_tool(
    doctor_name: str,
    patient_name: str,
    patient_email: str,
    date_time: datetime,
    symptoms: str | None = None,
) -> str:
    """Book an appointment and trigger side effects required by the assignment."""
    await _ensure_db_initialized()
    booking_message = await book_appointment_db_helper(
        doctor_name=doctor_name,
        patient_name=patient_name,
        date_time=date_time,
        symptoms=symptoms,
    )

    booked = booking_message.startswith("Appointment booked for")
    result = {
        "ok": booked,
        "tool": "book_appointment_tool",
        "doctor_name": doctor_name,
        "patient_name": patient_name,
        "patient_email": patient_email,
        "date_time": date_time.isoformat(),
        "message": booking_message,
    }

    if not booked:
        return _as_json(result)

    try:
        email_delivery = await send_booking_confirmation(
            patient_email=patient_email,
            patient_name=patient_name,
            doctor_name=doctor_name,
            date_time=date_time.isoformat(),
        )
        result["email"] = {
            "ok": True,
            "provider": "resend",
            "response": str(email_delivery),
        }
    except Exception as exc:
        result["email"] = {
            "ok": False,
            "provider": "resend",
            "message": f"Failed to send confirmation email: {exc}",
        }

    return _as_json(result)


@mcp.tool()
async def get_daily_stats(date: str) -> str:
    """Return daily appointment stats used by doctor reporting flows."""
    await _ensure_db_initialized()
    stats = await get_daily_stats_db(date)
    if not stats.get("ok"):
        return _as_json(stats)

    stats["tool"] = "get_daily_stats"
    stats["summary"] = (
        f"You have {stats['appointment_count']} appointments on {stats['date']}. "
        f"{stats['fever_mentions']} patients reported fever."
    )
    return _as_json(stats)


@mcp.tool()
async def send_doctor_report_notification(doctor_name: str, doctor_email: str, date: str) -> str:
    """Generate a doctor report and notify via Slack (non-email channel)."""
    await _ensure_db_initialized()
    stats = await get_daily_stats_db(date)
    if not stats.get("ok"):
        return _as_json(
            {
                "ok": False,
                "tool": "send_doctor_report_notification",
                "date": date,
                "message": stats.get("message", "Unable to fetch daily stats."),
                "notification": {
                    "ok": False,
                    "channel": "slack",
                    "message": "Skipped because stats query failed.",
                },
            }
        )

    report = (
        f"You have {stats['appointment_count']} appointments on {stats['date']}. "
        f"{stats['fever_mentions']} patients reported fever."
    )

    notification = await send_doctor_report_to_slack(
        doctor_name=doctor_name,
        doctor_email=doctor_email,
        date=date,
        report_text=report,
    )

    return _as_json(
        {
            "ok": notification.get("ok", False),
            "tool": "send_doctor_report_notification",
            "doctor_name": doctor_name,
            "doctor_email": doctor_email,
            "date": date,
            "report": report,
            "stats": stats,
            "notification": notification,
        }
    )


if __name__ == "__main__":
    mcp.run(transport='sse')