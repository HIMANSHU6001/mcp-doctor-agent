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
) -> Dict[str, Any]:
    """Send a doctor report notification using an incoming Slack webhook."""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return {
            "ok": False,
            "channel": "slack",
            "message": "SLACK_WEBHOOK_URL is missing.",
        }

    payload = {
        "text": f"Doctor report for {doctor_name} ({date})",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Doctor Report: {doctor_name}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Doctor*\\n{doctor_name}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Email*\\n{doctor_email}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Date*\\n{date}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Generated At*\\n{datetime.utcnow().isoformat()}Z",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": report_text,
                },
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
