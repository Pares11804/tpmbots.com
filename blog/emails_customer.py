"""Transactional email for TPMBOTS customers (verification, draft review)."""

from __future__ import annotations

import html

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives

from blog.models import BlogEntry


def send_email_verification(*, user: User, verify_url: str) -> None:
    subject = "Confirm your email — TPMBOTS"
    text = (
        f"Hi,\n\n"
        f"Please confirm your email for TPMBOTS by opening this link:\n{verify_url}\n\n"
        f"If you did not register, you can ignore this message.\n"
    )
    safe_url = html.escape(verify_url)
    html_body = f"""
<html><body style="font-family: system-ui, sans-serif; line-height: 1.6;">
  <h2>Confirm your email</h2>
  <p><a href="{safe_url}">Click here to verify your TPMBOTS account</a></p>
  <p style="color:#666;font-size:0.9em;">Or paste this URL into your browser:<br>{safe_url}</p>
</body></html>
"""
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def send_customer_draft_email(*, entry: BlogEntry, dashboard_url: str) -> None:
    if not entry.owner_id or not entry.owner.email:
        return
    title = entry.title or "Your blog draft"
    subject = f"[TPMBOTS] Draft ready for review — {title}"
    text = (
        f"We have a draft ready for your scheduled publication.\n\n"
        f"Title: {title}\n\n"
        f"Review, edit if needed, and approve in your dashboard:\n{dashboard_url}\n\n"
        f"The post will only go live at your scheduled time after you approve.\n"
    )
    safe_title = html.escape(title)
    safe_url = html.escape(dashboard_url)
    html_body = f"""
<html><body style="font-family: system-ui, sans-serif; line-height: 1.6;">
  <h2>Draft ready for review</h2>
  <p><strong>{safe_title}</strong></p>
  <p><a href="{safe_url}">Open your TPMBOTS dashboard</a> to edit and approve.</p>
  <p style="color:#666;font-size:0.9em;">Nothing is published to your site until you approve and the scheduled time arrives.</p>
</body></html>
"""
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[entry.owner.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def send_customer_blog_review_email(
    *,
    entry: BlogEntry,
    dashboard_url: str,
    wp_admin_url: str,
    public_url: str,
    one_click_publish_url: str,
    wp_draft_ok: bool,
) -> None:
    """After Mistral + optional WordPress draft: email customer links to edit, review in TPMBOTS, or one-click publish."""
    if not entry.owner_id or not entry.owner.email:
        return
    title = entry.title or "Your blog draft"
    subject = f"[TPMBOTS] Your draft — review & publish — {title}"
    safe_title = html.escape(title)
    safe_dash = html.escape(dashboard_url)
    safe_admin = html.escape(wp_admin_url)
    safe_public = html.escape(public_url)
    safe_publish = html.escape(one_click_publish_url)

    if wp_draft_ok:
        text = (
            f"Your notes were expanded with AI and saved as a draft on WordPress.\n\n"
            f"Title: {title}\n"
            f"WordPress post ID: {entry.wordpress_post_id}\n\n"
            f"Edit in WordPress:\n{wp_admin_url}\n\n"
            f"Public URL:\n{public_url}\n\n"
            f"Review in TPMBOTS (edit, approve to go live, or discard):\n{dashboard_url}\n\n"
            f"One-click publish (single-use):\n{one_click_publish_url}\n"
        )
        html_body = f"""
<html><body style="font-family: system-ui, sans-serif; line-height: 1.6;">
  <h2>Your WordPress draft is ready</h2>
  <p><strong>{safe_title}</strong></p>
  <p><strong>Post ID:</strong> {entry.wordpress_post_id}</p>
  <ol>
    <li><a href="{safe_admin}">Edit in WordPress</a></li>
    <li><a href="{safe_public}">Open public URL</a> (preview while still draft)</li>
    <li><a href="{safe_dash}">TPMBOTS</a> — edit, <strong>Approve &amp; publish live</strong>, or <strong>Discard</strong></li>
    <li><a href="{safe_publish}"><strong>Publish now (one click)</strong></a></li>
  </ol>
  <p style="color:#666;font-size:0.9em;">The one-click link stops working after a successful publish.</p>
</body></html>
"""
    else:
        text = (
            f"Your post was generated with AI, but creating a WordPress draft failed.\n\n"
            f"Title: {title}\n\n"
            f"Open TPMBOTS to review the text:\n{dashboard_url}\n"
        )
        html_body = f"""
<html><body style="font-family: system-ui, sans-serif; line-height: 1.6;">
  <h2>Draft text ready — WordPress upload failed</h2>
  <p><strong>{safe_title}</strong></p>
  <p>Open <a href="{safe_dash}">TPMBOTS</a> to review. After WordPress credentials are fixed, use <strong>Approve &amp; publish live</strong> to create the draft and publish.</p>
</body></html>
"""

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[entry.owner.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
