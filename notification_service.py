from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict
from urllib import error, request


async def send_doctor_report_to_slack(
    *,
    doctor_name: str,
    doctor_email: str,
    date: str,
    report_text: str,
    stats: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Send a doctor report notification using an incoming Slack webhook."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return {
            "ok": False,
            "channel": "slack",
            "message": "SLACK_WEBHOOK_URL is missing.",
        }

    appointment_count = int((stats or {}).get("appointment_count", 0))
    fever_mentions = int((stats or {}).get("fever_mentions", 0))

    payload = {
        "text": (
            f"Doctor report | {doctor_name} | {date} | "
            f"appointments={appointment_count}, fever_mentions={fever_mentions}"
        ),
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "Daily Doctor Report",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Doctor:* {doctor_name}  |  *Date:* {date}",
                },
            },
            {
                "type": "divider",
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Appointments*\n{appointment_count}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Fever Mentions*\n{fever_mentions}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*Notification Channel*\nSlack Webhook",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Generated At (UTC)*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}Z",
                    },
                ],
            },
            {
                "type": "divider",
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Summary*\n{report_text}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Doctor email: {doctor_email}",
                    }
                ],
            },
        ],
    }

    body = json.dumps(payload).encode("utf-8")

    def _post() -> tuple[int, str]:
        req = request.Request(
            webhook_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=12) as response:
            response_body = response.read().decode("utf-8")
            return response.status, response_body

    try:
        status_code, response_text = await asyncio.to_thread(_post)
    except error.HTTPError as exc:
        return {
            "ok": False,
            "channel": "slack",
            "message": f"Slack webhook failed: {exc.code} {exc.reason}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "channel": "slack",
            "message": f"Slack webhook failed: {exc}",
        }

    return {
        "ok": status_code == 200,
        "channel": "slack",
        "status_code": status_code,
        "response": response_text,
    }
