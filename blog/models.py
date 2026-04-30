from __future__ import annotations

from datetime import time

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class SubscriptionTier(models.TextChoices):
    """High-level plan; price uses posts_per_week for multi-frequency text plans."""

    TEXT_WEEKLY = "text_weekly", "Text only — 1 post per week ($20/mo)"
    TEXT_CUSTOM = "text_custom", "Text only — custom posts per week ($20 × posts per week / mo)"
    IMAGES_FOUR = "images_four", "Formatted text + 1–2 images — up to 4 blogs per month ($30/mo)"


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=64, blank=True)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)

    tier = models.CharField(
        max_length=32,
        choices=SubscriptionTier.choices,
        blank=True,
    )
    posts_per_week = models.PositiveSmallIntegerField(
        default=1,
        help_text="For text plans: 1 = weekly, 2 = twice per week, etc. Multiplies $20/mo base.",
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_started_at = models.DateTimeField(null=True, blank=True)
    billing_setup_complete = models.BooleanField(
        default=False,
        help_text="Customer confirmed payment method on file (integrate Stripe when ready).",
    )
    paid_current_period = models.BooleanField(
        default=False,
        help_text="After the free trial, set True when payment succeeds (e.g. Stripe webhook or admin).",
    )

    publish_weekday = models.PositiveSmallIntegerField(
        default=2,
        help_text="0=Monday … 6=Sunday — preferred weekly publish day.",
    )
    publish_timezone = models.CharField(
        max_length=64,
        default=settings.TIME_ZONE,
        help_text="IANA timezone for publish day and time (e.g. America/New_York).",
    )
    publish_time = models.TimeField(default=time(10, 0), help_text="Local time on publish day.")
    draft_lead_hours = models.PositiveSmallIntegerField(
        default=48,
        help_text="How many hours before publish time we email the draft for review.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile · {self.user.email or self.user.username}"

    @property
    def subscription_ready(self) -> bool:
        return bool(self.tier) and self.billing_setup_complete and self.email_verified

    @property
    def trial_active(self) -> bool:
        if not self.trial_ends_at:
            return False
        return timezone.now() < self.trial_ends_at

    def can_submit_blogs(self) -> bool:
        if not self.subscription_ready:
            return False
        if self.trial_active:
            return True
        return self.paid_current_period

    def monthly_price_usd(self) -> int:
        """Advertised monthly USD from tier and frequency (integer for display)."""
        if self.tier == SubscriptionTier.TEXT_WEEKLY:
            return 20
        if self.tier == SubscriptionTier.TEXT_CUSTOM:
            return 20 * max(1, int(self.posts_per_week))
        if self.tier == SubscriptionTier.IMAGES_FOUR:
            return 30
        return 0


class BlogEntry(models.Model):
    """Customer brief or legacy Mistral→WordPress pipeline."""

    class ApprovalStatus(models.TextChoices):
        NONE = "none", "N/A (legacy pipeline)"
        PENDING_CUSTOMER = "pending_customer", "Awaiting customer review"
        APPROVED = "approved", "Approved — scheduled"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected / cancelled"

    owner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="blog_entries",
    )
    customer_brief = models.TextField(blank=True, help_text="Customer-supplied lines / brief (formatted text).")
    customer_edited_body = models.TextField(blank=True, help_text="Last saved version from customer before approval.")
    approval_status = models.CharField(
        max_length=32,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.NONE,
    )
    scheduled_publish_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the post may go live (UTC) if approved.",
    )
    draft_email_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When we email the draft (publish minus lead hours).",
    )
    draft_notification_sent_at = models.DateTimeField(null=True, blank=True)
    wp_draft_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When an approved draft was pushed to WordPress as draft.",
    )

    title = models.CharField(max_length=500, blank=True)
    oracle_script = models.TextField(blank=True)
    generated_body = models.TextField(blank=True)
    mistral_model = models.CharField(max_length=100, default="mistral-large-latest")
    wordpress_category_name = models.CharField(max_length=200, blank=True)
    wordpress_post_id = models.PositiveIntegerField(null=True, blank=True)
    wordpress_post_type = models.CharField(max_length=20, default="post")
    wordpress_status = models.CharField(max_length=20, default="draft")
    publish_error = models.TextField(blank=True)
    publish_secret_token = models.CharField(max_length=64, blank=True)
    email_notify_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title or f"BlogEntry #{self.pk}"

    def effective_body_text(self) -> str:
        # Prefer user edits, then AI-generated post, then raw customer brief / legacy bodies.
        return (
            self.customer_edited_body
            or self.generated_body
            or self.customer_brief
            or self.oracle_script
            or ""
        ).strip()

    def is_customer_submission(self) -> bool:
        return self.owner_id is not None and bool(
            self.customer_brief or self.customer_edited_body or self.generated_body
        )
