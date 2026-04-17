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
    locked_dates: list[datetime.date],
    watch_name: str | None,
    dashboard_url: str,
) -> str:
    # Available dates section
    avail_section = ""
    if available_dates:
        dates_str = ", ".join(d.strftime("%b %d") for d in sorted(available_dates))
        avail_section = f"""
        <p style="color: #333; font-size: 16px;">
            <strong>Available now:</strong> {dates_str}
        </p>
        <a href="{booking_url}"
           style="display: inline-block; margin-top: 8px; padding: 10px 20px;
                  background: #2d5016; color: white; text-decoration: none;
                  border-radius: 6px; font-weight: 600;">
            Book Now
        </a>
        """

    # Locked dates section (ReserveCalifornia cancellations)
    locked_section = ""
    if locked_dates:
        locked_items = "".join(
            f"<li>Site unlocks at <strong>8:00 AM PT on {d.strftime('%b %d')}</strong></li>"
            for d in sorted(locked_dates)
        )
        locked_section = f"""
        <div style="margin-top: 16px; padding: 12px; background: #fef3c7; border-radius: 6px;">
            <p style="margin: 0 0 8px; font-weight: 600; color: #92400e;">
                Cancellation detected — be ready!
            </p>
            <ul style="margin: 0; padding-left: 20px; color: #92400e;">{locked_items}</ul>
            <a href="{booking_url}"
               style="display: inline-block; margin-top: 8px; padding: 8px 16px;
                      background: #92400e; color: white; text-decoration: none;
                      border-radius: 6px; font-weight: 600; font-size: 14px;">
                Go to booking page
            </a>
        </div>
        """

    return f"""
    <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #2d5016;">New availability at {facility_name}</h2>
        {avail_section}
        {locked_section}
        <hr style="margin-top: 24px; border: none; border-top: 1px solid #d4c4a8;">
        <p style="margin-top: 12px; color: #999; font-size: 13px;">
            {watch_name or "Availability watch"}<br>
            <a href="{dashboard_url}" style="color: #2d5016;">Manage your alerts</a>
        </p>
    </div>
    """


async def send_availability_alert(
    to_email: str,
    facility_name: str,
    booking_url: str,
    available_dates: list[datetime.date],
    watch_name: str | None,
    locked_dates: list[datetime.date] | None = None,
) -> bool:
    """Send an availability alert email. Returns True on success."""
    settings = get_settings()
    resend.api_key = settings.resend_api_key
    dashboard_url = f"{settings.frontend_url}/dashboard"

    html = _render_html(
        facility_name,
        booking_url,
        available_dates,
        locked_dates or [],
        watch_name,
        dashboard_url,
    )

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
