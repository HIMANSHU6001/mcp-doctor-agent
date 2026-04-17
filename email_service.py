from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict

import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


def _build_resend_error_message(exc: Exception) -> str:
    """Convert provider exceptions into actionable setup guidance."""
    raw_message = str(exc)
    normalized = raw_message.lower()

    if "testing emails" in normalized or "verify a domain" in normalized:
        return (
            "Resend is in testing mode and can only email verified recipients. "
            "Verify a domain in Resend and set RESEND_FROM_EMAIL to a sender on that domain."
        )
    if "invalid api key" in normalized or "unauthorized" in normalized:
        return "RESEND_API_KEY is invalid or unauthorized. Update it in the environment."
    if "from" in normalized and "address" in normalized:
        return (
            "The sender address is not allowed by Resend. "
            "Set RESEND_FROM_EMAIL to a verified sender address."
        )
    if "invalid" in normalized and "email" in normalized:
        return "Recipient email address is invalid. Confirm the patient's email value."

    return f"Resend provider error: {raw_message}"


async def send_booking_confirmation(
    patient_email: str,
    patient_name: str,
    doctor_name: str,
    date_time: str,
):
    """Send a booking confirmation email through Resend."""
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is missing. Set it in the .env file.")

    try:
        appointment_time = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        formatted_time = appointment_time.strftime("%A, %B %d, %Y at %I:%M %p")
    except ValueError:
        formatted_time = date_time

    subject = f"Appointment Confirmation with {doctor_name}"
    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937;">
      <h2 style="color: #0f766e;">Appointment Confirmed</h2>
      <p>Hi {patient_name},</p>
      <p>Your appointment has been confirmed with <strong>{doctor_name}</strong>.</p>
      <p><strong>Date and time:</strong> {formatted_time}</p>
      <p>If you need to reschedule, please contact our support team.</p>
      <p>Best regards,<br/>Doctor Assistant Team</p>
    </div>
    """

    payload = {
        "from": RESEND_FROM_EMAIL or "onboarding@resend.dev",
        "to": [patient_email],
        "subject": subject,
        "html": html,
    }

    try:
        return await asyncio.to_thread(resend.Emails.send, payload)
    except Exception as exc:
        actionable_message = _build_resend_error_message(exc)
        raise RuntimeError(f"{actionable_message} Provider details: {exc}") from exc


async def send_doctor_appointment_notification(
    doctor_email: str,
    doctor_name: str,
    patient_name: str,
    patient_email: str,
    date_time: str,
    symptoms: str | None = None,
):
    """Notify the doctor that a new appointment has been scheduled."""
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is missing. Set it in the .env file.")

    try:
        appointment_time = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        formatted_time = appointment_time.strftime("%A, %B %d, %Y at %I:%M %p")
    except ValueError:
        formatted_time = date_time

    safe_symptoms = symptoms.strip() if symptoms else "Not provided"

    subject = f"New Appointment Scheduled: {patient_name}"
    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937;">
      <h2 style="color: #0f766e;">New Appointment Scheduled</h2>
      <p>Hi {doctor_name},</p>
      <p>A new appointment has been scheduled with your clinic.</p>
      <p><strong>Patient:</strong> {patient_name}</p>
      <p><strong>Patient email:</strong> {patient_email}</p>
      <p><strong>Date and time:</strong> {formatted_time}</p>
      <p><strong>Symptoms:</strong> {safe_symptoms}</p>
      <p>Regards,<br/>Doctor Assistant Team</p>
    </div>
    """

    payload = {
        "from": RESEND_FROM_EMAIL or "onboarding@resend.dev",
        "to": [doctor_email],
        "subject": subject,
        "html": html,
    }

    try:
        return await asyncio.to_thread(resend.Emails.send, payload)
    except Exception as exc:
        actionable_message = _build_resend_error_message(exc)
        raise RuntimeError(f"{actionable_message} Provider details: {exc}") from exc


async def send_doctor_daily_report_email(
    doctor_email: str,
    doctor_name: str,
    date: str,
    report_text: str,
    stats: Dict[str, Any] | None = None,
):
    """Send the doctor's daily report summary over email."""
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY is missing. Set it in the .env file.")

    appointment_count = int((stats or {}).get("appointment_count", 0))
    fever_mentions = int((stats or {}).get("fever_mentions", 0))

    subject = f"Daily Report for {date}"
    html = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1f2937;">
      <h2 style="color: #0f766e;">Daily Doctor Report</h2>
      <p>Hi {doctor_name},</p>
      <p>Here is your report for <strong>{date}</strong>.</p>
      <ul>
        <li><strong>Appointments:</strong> {appointment_count}</li>
        <li><strong>Fever mentions:</strong> {fever_mentions}</li>
      </ul>
      <p><strong>Summary:</strong> {report_text}</p>
      <p>Regards,<br/>Doctor Assistant Team</p>
    </div>
    """

    payload = {
        "from": RESEND_FROM_EMAIL or "onboarding@resend.dev",
        "to": [doctor_email],
        "subject": subject,
        "html": html,
    }

    try:
        return await asyncio.to_thread(resend.Emails.send, payload)
    except Exception as exc:
        actionable_message = _build_resend_error_message(exc)
        raise RuntimeError(f"{actionable_message} Provider details: {exc}") from exc