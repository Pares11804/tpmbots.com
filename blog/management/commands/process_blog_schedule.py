"""
Send draft-review emails when draft_email_at is reached, and publish approved posts
when scheduled_publish_at is reached. Run from cron, e.g. every 5–15 minutes:

    python manage.py process_blog_schedule
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.emails_customer import send_customer_draft_email
from blog.models import BlogEntry
from blog.services import wordpress_xmlrpc


class Command(BaseCommand):
    help = "Send due draft emails and publish approved WordPress drafts at scheduled time."

    def handle(self, *args, **options):
        now = timezone.now()
        sent = self._send_draft_emails(now)
        published = self._publish_due(now)
        self.stdout.write(self.style.SUCCESS(f"Draft emails sent: {sent}; posts published: {published}"))

    def _send_draft_emails(self, now) -> int:
        qs = BlogEntry.objects.filter(
            owner__isnull=False,
            approval_status=BlogEntry.ApprovalStatus.PENDING_CUSTOMER,
            draft_notification_sent_at__isnull=True,
            draft_email_at__lte=now,
        ).select_related("owner")
        count = 0
        site = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        for entry in qs:
            url = f"{site}/dashboard/entry/{entry.pk}/"
            try:
                send_customer_draft_email(entry=entry, dashboard_url=url)
            except Exception as exc:
                entry.email_notify_error = str(exc)
                entry.save(update_fields=["email_notify_error", "updated_at"])
                self.stderr.write(f"Entry {entry.pk}: email failed: {exc}")
                continue
            entry.draft_notification_sent_at = now
            entry.email_notify_error = ""
            entry.save(update_fields=["draft_notification_sent_at", "email_notify_error", "updated_at"])
            count += 1
        return count

    def _publish_due(self, now) -> int:
        qs = BlogEntry.objects.filter(
            owner__isnull=False,
            approval_status=BlogEntry.ApprovalStatus.APPROVED,
            scheduled_publish_at__lte=now,
            wordpress_post_id__isnull=False,
        ).exclude(wordpress_status="publish")
        count = 0
        for entry in qs:
            if not entry.wordpress_post_id:
                entry.publish_error = "No WordPress draft ID — approve step may have failed."
                entry.save(update_fields=["publish_error", "updated_at"])
                continue
            try:
                wordpress_xmlrpc.promote_draft_to_publish(post_id=entry.wordpress_post_id)
            except (ValueError, RuntimeError) as exc:
                entry.publish_error = str(exc)
                entry.save(update_fields=["publish_error", "updated_at"])
                self.stderr.write(f"Entry {entry.pk}: publish failed: {exc}")
                continue
            entry.wordpress_status = "publish"
            entry.approval_status = BlogEntry.ApprovalStatus.PUBLISHED
            entry.publish_error = ""
            entry.publish_secret_token = ""
            entry.save(
                update_fields=[
                    "wordpress_status",
                    "approval_status",
                    "publish_error",
                    "publish_secret_token",
                    "updated_at",
                ]
            )
            count += 1
        return count
