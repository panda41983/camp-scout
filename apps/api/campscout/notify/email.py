"""Send availability alert emails via Resend."""
from __future__ import annotations

import datetime

import resend
import structlog

from campscout.config import get_settings

log = structlog.get_logger()


def _render_html(
    facility_name: str,
    booking_url: str,
    available_dates: list[datetime.date],
    watch_name: str | None,
) -> str:
    dates_str = ", ".join(d.strftime("%b %d") for d in sorted(available_dates))
    return f"""
    <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #1a1a1a;">New availability at {facility_name}</h2>
        <p style="color: #555; font-size: 16px;">
            {facility_name} has openings on: <strong>{dates_str}</strong>
        </p>
        <a href="{booking_url}"
           style="display: inline-block; margin-top: 12px; padding: 10px 20px;
                  background: #ef4444; color: white; text-decoration: none;
                  border-radius: 6px; font-weight: 600;">
            Book on Recreation.gov
        </a>
        <p style="margin-top: 24px; color: #999; font-size: 13px;">
            {watch_name or "Availability watch"}<br>
            Sent by CampScout
        </p>
    </div>
    """


async def send_availability_alert(
    to_email: str,
    facility_name: str,
    booking_url: str,
    available_dates: list[datetime.date],
    watch_name: str | None,
) -> bool:
    """Send an availability alert email. Returns True on success."""
    settings = get_settings()
    resend.api_key = settings.resend_api_key

    html = _render_html(facility_name, booking_url, available_dates, watch_name)

    try:
        resend.Emails.send({
            "from": settings.notify_from_email,
            "to": [to_email],
            "subject": f"New availability at {facility_name}",
            "html": html,
        })
        log.info("email_sent", to=to_email, facility=facility_name)
        return True
    except Exception:
        log.exception("email_send_failed", to=to_email, facility=facility_name)
        return False
