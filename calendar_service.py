from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict

from google.oauth2 import service_account
from googleapiclient.discovery import build

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _load_service_account_info() -> Dict[str, Any] | None:
    """Resolve service account configuration from env JSON or file path."""
    service_account_json = os.getenv("GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON", "").strip()
    if service_account_json:
        try:
            if service_account_json.startswith("{"):
                parsed = json.loads(service_account_json)
            else:
                with open(service_account_json, "r", encoding="utf-8") as handle:
                    parsed = json.load(handle)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None

    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
    if service_account_file:
        try:
            with open(service_account_file, "r", encoding="utf-8") as handle:
                parsed = json.load(handle)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None

    return None


def _resolve_calendar_id(doctor_name: str) -> str | None:
    mapped_json = os.getenv("GOOGLE_CALENDAR_MAP_JSON", "").strip()
    if mapped_json:
        try:
            mapping = json.loads(mapped_json)
            if isinstance(mapping, dict):
                doctor_calendar = mapping.get(doctor_name)
                if isinstance(doctor_calendar, str) and doctor_calendar.strip():
                    return doctor_calendar.strip()
        except json.JSONDecodeError:
            pass

    default_calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "").strip()
    if default_calendar_id:
        return default_calendar_id

    return None


def _build_calendar_service() -> Any:
    service_account_info = _load_service_account_info()
    if not service_account_info:
        raise RuntimeError(
            "Google Calendar service account is not configured. "
            "Set GOOGLE_SERVICE_ACCOUNT_FILE or GOOGLE_CALENDAR_SERVICE_ACCOUNT_JSON."
        )

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=CALENDAR_SCOPES,
    )
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


async def create_calendar_event(
    *,
    doctor_name: str,
    patient_name: str,
    patient_email: str,
    date_time: datetime,
    symptoms: str | None = None,
) -> Dict[str, Any]:
    """Create a Google Calendar event for a booked appointment."""
    calendar_id = _resolve_calendar_id(doctor_name)
    if not calendar_id:
        return {
            "ok": False,
            "message": (
                "Calendar ID is missing. Set GOOGLE_CALENDAR_ID or GOOGLE_CALENDAR_MAP_JSON."
            ),
        }

    timezone = os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Asia/Kolkata")
    start_time = date_time
    end_time = date_time + timedelta(minutes=30)

    event_payload = {
        "summary": f"Appointment: {patient_name} with {doctor_name}",
        "description": (
            f"Patient: {patient_name}\\n"
            f"Patient Email: {patient_email}\\n"
            f"Symptoms: {symptoms or 'Not provided'}"
        ),
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": timezone,
        },
        "attendees": [{"email": patient_email}],
    }

    def _create_event() -> Dict[str, Any]:
        service = _build_calendar_service()
        return (
            service.events()
            .insert(calendarId=calendar_id, body=event_payload, sendUpdates="all")
            .execute()
        )

    try:
        event = await asyncio.to_thread(_create_event)
        return {
            "ok": True,
            "calendar_id": calendar_id,
            "event_id": event.get("id"),
            "event_link": event.get("htmlLink"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Failed to create Google Calendar event: {exc}",
        }
