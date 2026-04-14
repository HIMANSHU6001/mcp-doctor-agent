from __future__ import annotations

import asyncio
import os
from datetime import datetime

import resend

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


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
        "from": "onboarding@resend.dev",
        "to": [patient_email],
        "subject": subject,
        "html": html,
    }

    return await asyncio.to_thread(resend.Emails.send, payload)