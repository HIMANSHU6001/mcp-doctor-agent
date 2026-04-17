from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import httpx


async def send_doctor_report_to_slack(
    *,
    doctor_name: str,
    doctor_email: str,
    date: str,
    report_text: str,
    bot_token: str,
    user_id: str,
    stats: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Send a doctor report notification to a doctor's Slack DM."""
    if not bot_token or not user_id:
        return {
            "ok": False,
            "channel": "slack",
            "status": "not_connected",
            "message": "Connect to Slack to get report on your Slack.",
        }

    appointment_count = int((stats or {}).get("appointment_count", 0))
    fever_mentions = int((stats or {}).get("fever_mentions", 0))

    payload = {
        "text": (
            f"Doctor report | {doctor_name} | {date} | "
            f"appointments={appointment_count}, fever_mentions={fever_mentions}"
        ),
        "channel": user_id,
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
                        "text": "*Notification Channel*\nSlack DM",
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

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={
                    "Authorization": f"Bearer {bot_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except Exception as exc:
        return {
            "ok": False,
            "channel": "slack",
            "status": "failed",
            "message": f"Slack DM failed: {exc}",
        }

    try:
        response_payload = response.json()
    except ValueError:
        return {
            "ok": False,
            "channel": "slack",
            "status": "failed",
            "message": "Slack DM failed: invalid response from Slack API.",
        }

    if not response_payload.get("ok"):
        return {
            "ok": False,
            "channel": "slack",
            "status": "failed",
            "message": f"Slack API error: {response_payload.get('error', 'unknown_error')}",
        }

    return {
        "ok": True,
        "channel": "slack",
        "status": "sent",
        "message": "Report sent to Slack.",
        "ts": response_payload.get("ts"),
    }
