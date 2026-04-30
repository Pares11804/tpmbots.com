"""Resolve customer publish timezone for scheduling."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from blog.models import CustomerProfile


def zone_for_profile(profile: CustomerProfile):
    """Return a tzinfo for scheduling (falls back to Django default)."""
    name = (getattr(profile, "publish_timezone", None) or "").strip() or getattr(
        settings, "TIME_ZONE", "UTC"
    )
    try:
        return ZoneInfo(name)
    except Exception:
        try:
            return ZoneInfo(getattr(settings, "TIME_ZONE", "UTC"))
        except Exception:
            return timezone.get_current_timezone()
