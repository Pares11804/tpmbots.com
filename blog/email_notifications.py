"""Send email when a WordPress draft is created from a script."""

from __future__ import annotations

import html

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from blog.models import BlogEntry


def send_draft_created_email(
    *,
    entry: BlogEntry,
    admin_edit_url: str,
    one_click_publish_url: str,
    public_preview_url: str,
) -> None:
    to = getattr(settings, "NOTIFICATION_EMAIL", "") or "vaatrak@gmail.com"
    safe_title = html.escape(entry.title or "WordPress draft")
    subject = f"[Blog pipeline] Draft ready — {entry.title or 'WordPress draft'}"

    text_body = (
        f"A new WordPress draft was created from your script.\n\n"
        f"Title: {entry.title}\n"
        f"WordPress post ID: {entry.wordpress_post_id}\n\n"
        f"Review / edit in wp-admin (log in if asked):\n{admin_edit_url}\n\n"
        f"Public URL (after you publish, or preview while logged in):\n{public_preview_url}\n\n"
        f"One-click PUBLISH (opens in browser, no WordPress login needed):\n{one_click_publish_url}\n\n"
        f"If the publish link stops working, the draft may already be live or the link was already used.\n"
    )

    html_body = f"""
<html><body style="font-family: system-ui, sans-serif; line-height: 1.5;">
  <h2>Draft created</h2>
  <p><strong>Title:</strong> {safe_title}</p>
  <p><strong>WordPress post ID:</strong> {entry.wordpress_post_id}</p>
  <ol>
    <li><a href="{admin_edit_url}">Open draft in WordPress admin</a> (edit / validate)</li>
    <li><a href="{public_preview_url}">Open public post URL</a> (works when published; drafts usually need login)</li>
    <li><a href="{one_click_publish_url}"><strong>Publish now</strong></a> — makes the post live</li>
  </ol>
  <p style="color:#666;font-size:0.9em;">One-click link is single-use–safe: it stops working after a successful publish.</p>
</body></html>
"""

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
