"""Compute next weekly publish slot and draft notification time (timezone-aware)."""

from __future__ import annotations

from datetime import datetime, timedelta
from datetime import time as time_type
from datetime import timezone as dt_timezone

from django.utils import timezone


def next_weekly_publish_utc(
    *,
    weekday: int,
    publish_time: time_type,
    tz,
    after: datetime | None = None,
) -> datetime:
    """
    Next occurrence of `weekday` (0=Monday … 6=Sunday) at `publish_time` in `tz`, as UTC.

    If today's slot matches but the local datetime is already past, use the same weekday next week.
    """
    tz = tz or timezone.get_current_timezone()
    after = after or timezone.now()
    if timezone.is_naive(after):
        after = timezone.make_aware(after, timezone.utc)
    local_after = after.astimezone(tz)
    target_dow = int(weekday) % 7

    for days_forward in range(0, 8):
        d = local_after.date() + timedelta(days=days_forward)
        if d.weekday() != target_dow:
            continue
        candidate_local = timezone.make_aware(datetime.combine(d, publish_time), tz)
        if candidate_local > local_after:
            return candidate_local.astimezone(dt_timezone.utc)

    # Fallback: one week ahead from first matching weekday
    d = local_after.date()
    while d.weekday() != target_dow:
        d += timedelta(days=1)
    candidate_local = timezone.make_aware(datetime.combine(d, publish_time), tz)
    if candidate_local <= local_after:
        candidate_local += timedelta(days=7)
    return candidate_local.astimezone(dt_timezone.utc)


def draft_email_at_utc(publish_at_utc: datetime, lead_hours: int) -> datetime:
    return publish_at_utc - timedelta(hours=max(0, int(lead_hours)))
