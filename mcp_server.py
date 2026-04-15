from __future__ import annotations

import asyncio
import json
from datetime import datetime

from mcp.server.fastmcp import FastMCP

from database import (
    book_appointment_db as book_appointment_db_helper,
    get_doctor_contact_by_name_db,
    get_daily_stats_db,
    get_doctor_availability as get_doctor_availability_helper,
    init_db,
    list_doctors_db,
)
from email_service import send_booking_confirmation, send_doctor_appointment_notification
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
        "booking_ok": booked,
        "tool": "book_appointment_tool",
        "doctor_name": doctor_name,
        "patient_name": patient_name,
        "patient_email": patient_email,
        "date_time": date_time.isoformat(),
        "message": booking_message,
        "email_sent": False,
        "patient_email_sent": False,
        "doctor_email_sent": False,
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
        result["patient_email"] = {
            "ok": True,
            "provider": "resend",
            "response": str(email_delivery),
        }
        result["email_sent"] = True
        result["patient_email_sent"] = True
    except Exception as exc:
        result["patient_email"] = {
            "ok": False,
            "provider": "resend",
            "message": f"Failed to send confirmation email: {exc}",
        }
        result["warning"] = "Appointment is booked, but the confirmation email could not be sent."

    doctor_contact = await get_doctor_contact_by_name_db(doctor_name=doctor_name)
    doctor_email = (
        doctor_contact.get("doctor", {}).get("email")
        if doctor_contact.get("ok")
        else None
    )

    if doctor_email:
        try:
            doctor_email_delivery = await send_doctor_appointment_notification(
                doctor_email=doctor_email,
                doctor_name=doctor_name,
                patient_name=patient_name,
                patient_email=patient_email,
                date_time=date_time.isoformat(),
                symptoms=symptoms,
            )
            result["doctor_email"] = {
                "ok": True,
                "provider": "resend",
                "recipient": doctor_email,
                "response": str(doctor_email_delivery),
            }
            result["doctor_email_sent"] = True
        except Exception as exc:
            result["doctor_email"] = {
                "ok": False,
                "provider": "resend",
                "recipient": doctor_email,
                "message": f"Failed to send doctor notification email: {exc}",
            }
    else:
        result["doctor_email"] = {
            "ok": False,
            "provider": "resend",
            "message": doctor_contact.get("message", "Doctor email is unavailable."),
        }

    patient_status = "sent" if result["patient_email_sent"] else "failed"
    doctor_status = "sent" if result["doctor_email_sent"] else "failed"
    result["message"] = (
        f"{booking_message} Patient confirmation email {patient_status}; "
        f"doctor notification email {doctor_status}."
    )

    return _as_json(result)


@mcp.tool()
async def list_doctors_tool() -> str:
    """List all available doctors."""
    await _ensure_db_initialized()
    doctors_payload = await list_doctors_db()
    if not doctors_payload.get("ok"):
        return _as_json(
            {
                "ok": False,
                "tool": "list_doctors_tool",
                "message": doctors_payload.get("message", "Unable to fetch doctors."),
            }
        )

    doctors = doctors_payload.get("doctors", [])
    if doctors:
        summary = ", ".join(doctor["name"] for doctor in doctors)
        message = f"Available doctors: {summary}."
    else:
        message = "No doctors are currently available."

    return _as_json(
        {
            "ok": True,
            "tool": "list_doctors_tool",
            "count": doctors_payload.get("count", 0),
            "doctors": doctors,
            "message": message,
        }
    )


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
        stats=stats,
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