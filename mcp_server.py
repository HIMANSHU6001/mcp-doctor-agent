from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from database import (
    book_appointment_db as book_appointment_db_helper,
    get_doctor_contact_by_name_db,
    get_doctor_slack_credentials_by_email,
    get_daily_stats_db,
    get_doctor_availability as get_doctor_availability_helper,
    init_db,
    list_doctors_db,
)
from email_service import (
    send_booking_confirmation,
    send_doctor_appointment_notification,
    send_doctor_daily_report_email,
)
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
        await init_db(reset_schema=False)
        _db_initialized = True


@mcp.prompt(name="patient_booking_prompt", description="Reusable prompt for patient appointment booking")
def patient_booking_prompt(
    doctor_name: str,
    date: str,
    patient_name: str | None = None,
) -> list[dict[str, str]]:
    resolved_patient_name = patient_name or "the patient"
    return [
        {
            "role": "system",
            "content": (
                "You are a patient appointment assistant. Use MCP tools to check availability, "
                "book the slot if requested, and clearly report booking and email delivery status."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{resolved_patient_name} wants to book an appointment with {doctor_name} on {date}. "
                "Check availability first, then book the appointment only if the requested slot is open."
            ),
        },
    ]


@mcp.prompt(name="doctor_report_prompt", description="Reusable prompt for doctor summary reporting")
def doctor_report_prompt(
    doctor_name: str,
    date: str | None = None,
) -> list[dict[str, str]]:
    target_date = date or "today"
    return [
        {
            "role": "system",
            "content": (
                "You are a doctor reporting assistant. Use MCP tools to fetch daily stats and "
                "send a report email always, then send Slack DM if Slack is connected."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Generate the daily summary for {doctor_name} for {target_date} and notify the doctor by email and Slack when available."
            ),
        },
    ]


@mcp.resource(
    "resource://doctor-assistant/guide",
    name="doctor_assistant_guide",
    description="Reusable workflow guide for the doctor assistant",
)
async def doctor_assistant_guide() -> dict[str, Any]:
    return {
        "app": "MCP Doctor Agent",
        "scenarios": {
            "patient": [
                "Check doctor availability",
                "Book a confirmed appointment",
                "Send patient and doctor notifications",
            ],
            "doctor": [
                "Fetch daily stats",
                "Summarize appointment volume and fever mentions",
                "Deliver an email report",
                "Deliver a Slack DM when connected",
            ],
        },
        "delivery_channels": {
            "patient_confirmation": "Resend email",
            "doctor_notification": "Resend email + Slack DM",
        },
        "sample_prompts": [
            "I want to book an appointment with Dr. Ahuja tomorrow morning.",
            "How many patients visited yesterday?",
            "Generate my daily report and notify me.",
        ],
    }


@mcp.resource(
    "resource://doctor-assistant/doctors/{doctor_name}",
    name="doctor_profile_resource",
    description="Read-only doctor profile and contact details",
)
async def doctor_profile_resource(doctor_name: str) -> dict[str, Any]:
    await _ensure_db_initialized()
    doctor_contact = await get_doctor_contact_by_name_db(doctor_name=doctor_name)
    if not doctor_contact.get("ok"):
        return {
            "ok": False,
            "doctor_name": doctor_name,
            "message": doctor_contact.get("message", "Doctor profile unavailable."),
        }

    return {
        "ok": True,
        "doctor": doctor_contact.get("doctor", {}),
        "message": f"Read-only profile for {doctor_name}.",
    }


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
    """Generate a doctor report and notify via email and optional Slack DM."""
    await _ensure_db_initialized()
    stats = await get_daily_stats_db(date)
    if not stats.get("ok"):
        return _as_json(
            {
                "ok": False,
                "tool": "send_doctor_report_notification",
                "date": date,
                "delivery_status": "failed",
                "message": stats.get("message", "Unable to fetch daily stats."),
                "delivery": {
                    "email": {
                        "ok": False,
                        "channel": "email",
                        "status": "skipped",
                        "message": "Skipped because stats query failed.",
                    },
                    "slack": {
                        "ok": False,
                        "channel": "slack",
                        "status": "skipped",
                        "message": "Skipped because stats query failed.",
                    },
                },
            }
        )

    report = (
        f"You have {stats['appointment_count']} appointments on {stats['date']}. "
        f"{stats['fever_mentions']} patients reported fever."
    )

    try:
        email_provider_response = await send_doctor_daily_report_email(
            doctor_email=doctor_email,
            doctor_name=doctor_name,
            date=date,
            report_text=report,
            stats=stats,
        )
        email_delivery = {
            "ok": True,
            "channel": "email",
            "status": "sent",
            "message": "Report sent to email.",
            "provider": "resend",
            "response": str(email_provider_response),
        }
    except Exception as exc:
        email_delivery = {
            "ok": False,
            "channel": "email",
            "status": "failed",
            "message": f"Email delivery failed: {exc}",
            "provider": "resend",
        }

    advisory: str | None = None
    slack_connected = False
    slack_delivery: dict[str, Any] = {
        "ok": False,
        "channel": "slack",
        "status": "not_connected",
        "message": "Connect to Slack to get report on your Slack.",
    }

    slack_credentials = await get_doctor_slack_credentials_by_email(doctor_email=doctor_email)
    if not slack_credentials.get("ok"):
        slack_delivery = {
            "ok": False,
            "channel": "slack",
            "status": "unavailable",
            "message": slack_credentials.get("message", "Could not read Slack credentials."),
        }
    else:
        doctor = slack_credentials.get("doctor", {})
        bot_token = str(doctor.get("slack_bot_token") or "").strip()
        user_id = str(doctor.get("slack_user_id") or "").strip()
        slack_connected = bool(bot_token and user_id)

        if slack_connected:
            slack_delivery = await send_doctor_report_to_slack(
                doctor_name=doctor_name,
                doctor_email=doctor_email,
                date=date,
                report_text=report,
                stats=stats,
                bot_token=bot_token,
                user_id=user_id,
            )
        else:
            advisory = "Connect to Slack to get report on your Slack."

    email_ok = bool(email_delivery.get("ok"))
    slack_ok = bool(slack_delivery.get("ok"))

    if email_ok and slack_connected and slack_ok:
        delivery_status = "all_success"
        message = "Report sent to email and Slack."
    elif email_ok and not slack_connected:
        delivery_status = "partial_success"
        advisory = advisory or "Connect to Slack to get report on your Slack."
        message = "Report sent to email. Connect to Slack to get report on your Slack."
    elif email_ok and slack_connected and not slack_ok:
        delivery_status = "partial_success"
        message = f"Report sent to email, but Slack delivery failed: {slack_delivery.get('message', 'Unknown Slack error.')}"
    elif not email_ok and slack_ok:
        delivery_status = "partial_success"
        message = f"Report sent to Slack, but email delivery failed: {email_delivery.get('message', 'Unknown email error.')}"
    else:
        delivery_status = "failed"
        message = "Unable to deliver the report by email or Slack."

    overall_ok = delivery_status != "failed"
    notification = {
        "ok": overall_ok,
        "delivery_status": delivery_status,
        "message": message,
        "email": email_delivery,
        "slack": slack_delivery,
    }

    return _as_json(
        {
            "ok": overall_ok,
            "tool": "send_doctor_report_notification",
            "doctor_name": doctor_name,
            "doctor_email": doctor_email,
            "date": date,
            "report": report,
            "stats": stats,
            "delivery_status": delivery_status,
            "delivery": {
                "email": email_delivery,
                "slack": slack_delivery,
            },
            "advisory": advisory,
            "message": message,
            "notification": notification,
        }
    )


if __name__ == "__main__":
    mcp.run(transport='sse')