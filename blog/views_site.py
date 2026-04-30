"""Marketing pages, registration, subscription, and customer dashboard."""

from __future__ import annotations

import random
import secrets
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from blog.customer_publish import create_wp_draft_for_entry
from blog.emails_customer import send_customer_blog_review_email, send_email_verification
from blog.forms_site import CustomerBlogForm, CustomerDraftEditForm, RegistrationForm, SubscriptionSetupForm
from blog.models import BlogEntry, CustomerProfile
from blog.scheduling import draft_email_at_utc, next_weekly_publish_utc
from blog.services import mistral_service, wordpress_xmlrpc
from blog.tzutil import zone_for_profile
from blog.utils import blog_body_to_html


def _image_library() -> list[str]:
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
    names: list[str] = []
    for dirname in ("images", "imaes"):
        image_dir = Path(settings.BASE_DIR) / dirname
        if not image_dir.exists():
            continue
        names.extend(
            p.name
            for p in image_dir.iterdir()
            if p.is_file() and p.suffix.lower() in allowed
        )
    return sorted(set(names))


def _issue_registration_captcha(request: HttpRequest) -> str:
    left = random.randint(1, 9)
    right = random.randint(1, 9)
    op = random.choice(["+", "-"])
    if op == "-" and right > left:
        left, right = right, left
    answer = left + right if op == "+" else left - right
    question = f"What is {left} {op} {right}?"
    request.session["registration_captcha_answer"] = str(answer)
    request.session["registration_captcha_question"] = question
    return question


def home(request: HttpRequest) -> HttpResponse:
    images = _image_library()
    featured = images[:3]
    return render(
        request,
        "blog/site/home.html",
        {"featured_images": featured},
    )


def pricing(request: HttpRequest) -> HttpResponse:
    return render(request, "blog/site/pricing.html")


def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")
    captcha_question = (request.session.get("registration_captcha_question") or "").strip()
    if not captcha_question:
        captcha_question = _issue_registration_captcha(request)

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            expected = (request.session.get("registration_captcha_answer") or "").strip()
            actual = (form.cleaned_data.get("captcha_answer") or "").strip()
            if not expected or actual != expected:
                form.add_error("captcha_answer", "Incorrect CAPTCHA answer. Please try again.")
                captcha_question = _issue_registration_captcha(request)
            else:
                email = form.cleaned_data["email"]
                password = form.cleaned_data["password1"]
                user = User.objects.create_user(username=email, email=email, password=password)
                token = secrets.token_urlsafe(32)
                CustomerProfile.objects.create(
                    user=user,
                    email_verified=False,
                    email_verification_token=token,
                    email_verification_sent_at=timezone.now(),
                )
                site = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
                verify_url = f"{site}/verify-email/?token={token}"
                try:
                    send_email_verification(user=user, verify_url=verify_url)
                except Exception as exc:
                    messages.warning(request, f"Account created but verification email failed: {exc}")
                else:
                    messages.success(
                        request,
                        "Check your inbox to confirm your email, then choose your subscription and schedule.",
                    )
                request.session.pop("registration_captcha_answer", None)
                request.session.pop("registration_captcha_question", None)
                return redirect("accounts_login")
        elif not captcha_question:
            captcha_question = _issue_registration_captcha(request)
    else:
        form = RegistrationForm()
    return render(request, "blog/site/register.html", {"form": form, "captcha_question": captcha_question})


def verify_email(request: HttpRequest) -> HttpResponse:
    token = (request.GET.get("token") or "").strip()
    if not token:
        messages.error(request, "Missing verification token.")
        return redirect("home")
    profile = CustomerProfile.objects.filter(email_verification_token=token).select_related("user").first()
    if not profile:
        messages.error(request, "Invalid or expired verification link.")
        return redirect("home")
    profile.email_verified = True
    profile.email_verification_token = ""
    profile.save(update_fields=["email_verified", "email_verification_token", "updated_at"])
    messages.success(request, "Email confirmed. Sign in to choose your plan and schedule.")
    return redirect("accounts_login")


@login_required
def subscribe(request: HttpRequest) -> HttpResponse:
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    if not profile.email_verified:
        messages.error(request, "Confirm your email before selecting a subscription.")
        return redirect("home")
    if profile.tier and profile.trial_ends_at:
        messages.info(request, "Your subscription is already set up.")
        return redirect("dashboard")
    if request.method == "POST":
        form = SubscriptionSetupForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            profile.subscription_started_at = timezone.now()
            profile.trial_ends_at = timezone.now() + timedelta(days=30)
            profile.save(update_fields=["subscription_started_at", "trial_ends_at", "updated_at"])
            messages.success(
                request,
                "Your plan and publishing schedule are saved. You have a one-month free trial from today.",
            )
            return redirect("dashboard")
    else:
        form = SubscriptionSetupForm(instance=profile)
    return render(request, "blog/site/subscribe.html", {"form": form, "profile": profile})


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    entries = BlogEntry.objects.filter(owner=request.user)[:50]
    return render(
        request,
        "blog/site/dashboard.html",
        {
            "profile": profile,
            "entries": entries,
            "can_post": profile.can_submit_blogs(),
        },
    )


@login_required
def dashboard_submit(request: HttpRequest) -> HttpResponse:
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    if not profile.can_submit_blogs():
        messages.error(request, "Complete subscription setup (and active trial or billing) before submitting posts.")
        return redirect("dashboard")
    if request.method == "POST":
        form = CustomerBlogForm(request.POST)
        if form.is_valid():
            title = (form.cleaned_data.get("title") or "").strip()
            brief = form.cleaned_data["customer_brief"].strip()
            cat = (form.cleaned_data.get("wordpress_category_name") or "").strip()
            try:
                generated = mistral_service.generate_blog_from_customer_brief(
                    title=title,
                    customer_brief=brief,
                    category_name=cat,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                return render(request, "blog/site/dashboard_submit.html", {"form": form, "profile": profile})
            except Exception as exc:
                messages.error(request, f"Could not generate post with Mistral: {exc}")
                return render(request, "blog/site/dashboard_submit.html", {"form": form, "profile": profile})

            tz = zone_for_profile(profile)
            publish_at = next_weekly_publish_utc(
                weekday=profile.publish_weekday,
                publish_time=profile.publish_time,
                tz=tz,
            )
            draft_at = draft_email_at_utc(publish_at, profile.draft_lead_hours)
            entry = BlogEntry.objects.create(
                owner=request.user,
                title=title,
                customer_brief=brief,
                customer_edited_body="",
                generated_body=generated,
                oracle_script="",
                mistral_model=mistral_service.DEFAULT_MISTRAL_MODEL,
                approval_status=BlogEntry.ApprovalStatus.PENDING_CUSTOMER,
                scheduled_publish_at=publish_at,
                draft_email_at=draft_at,
                wordpress_category_name=cat,
            )

            wp_base = (settings.WORDPRESS_URL or "").strip().rstrip("/")
            wp_ok = False
            try:
                create_wp_draft_for_entry(entry)
                entry.refresh_from_db()
                wp_ok = bool(entry.wordpress_post_id)
            except Exception as exc:
                entry.publish_error = str(exc)
                entry.save(update_fields=["publish_error", "updated_at"])

            now = timezone.now()
            site = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
            dashboard_url = f"{site}/dashboard/entry/{entry.pk}/"
            admin_url = f"{wp_base}/wp-admin/" if wp_base else ""
            public_url = ""
            one_click_url = dashboard_url
            if wp_ok and entry.wordpress_post_id:
                secret = secrets.token_urlsafe(32)
                entry.publish_secret_token = secret
                entry.wp_draft_created_at = now
                entry.publish_error = ""
                entry.save(
                    update_fields=[
                        "publish_secret_token",
                        "wp_draft_created_at",
                        "publish_error",
                        "updated_at",
                    ]
                )
                admin_url = f"{wp_base}/wp-admin/post.php?post={entry.wordpress_post_id}&action=edit"
                public_url = f"{wp_base}/?p={entry.wordpress_post_id}"
                one_click_url = f"{site}/publish/{entry.pk}/{secret}/"

            try:
                send_customer_blog_review_email(
                    entry=entry,
                    dashboard_url=dashboard_url,
                    wp_admin_url=admin_url,
                    public_url=public_url or (wp_base or ""),
                    one_click_publish_url=one_click_url,
                    wp_draft_ok=wp_ok,
                )
                entry.draft_notification_sent_at = now
                entry.email_notify_error = ""
                entry.save(update_fields=["draft_notification_sent_at", "email_notify_error", "updated_at"])
            except Exception as exc:
                entry.email_notify_error = str(exc)
                entry.save(update_fields=["email_notify_error", "updated_at"])
                messages.warning(request, f"Post saved but email failed: {exc}")

            if wp_ok:
                messages.success(
                    request,
                    "Mistral generated your post, a WordPress draft was created, and a review email was sent.",
                )
            else:
                messages.warning(
                    request,
                    "Mistral generated your post, but WordPress draft creation failed. Check WORDPRESS_* in .env, "
                    "then open this entry and use Approve to retry publishing.",
                )
            return redirect("customer_entry_detail", pk=entry.pk)
    else:
        form = CustomerBlogForm()
    return render(request, "blog/site/dashboard_submit.html", {"form": form, "profile": profile})


@login_required
def customer_entry_detail(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(BlogEntry, pk=pk, owner=request.user)
    profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
    edit_form = CustomerDraftEditForm(
        initial={
            "title": entry.title,
            "customer_edited_body": entry.customer_edited_body
            or entry.generated_body
            or entry.customer_brief,
        }
    )
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        if action == "save_draft":
            edit_form = CustomerDraftEditForm(request.POST)
            if edit_form.is_valid():
                entry.title = (edit_form.cleaned_data.get("title") or "").strip()
                entry.customer_edited_body = edit_form.cleaned_data["customer_edited_body"].strip()
                entry.save(update_fields=["title", "customer_edited_body", "updated_at"])
                messages.success(request, "Draft saved.")
                return redirect("customer_entry_detail", pk=entry.pk)
        elif action == "discard":
            if entry.approval_status != BlogEntry.ApprovalStatus.PENDING_CUSTOMER:
                messages.error(request, "Only pending submissions can be discarded.")
            else:
                entry.approval_status = BlogEntry.ApprovalStatus.REJECTED
                entry.save(update_fields=["approval_status", "updated_at"])
                messages.success(request, "Discarded. You can submit a new post from the dashboard.")
                return redirect("dashboard")
        elif action == "approve":
            edit_form = CustomerDraftEditForm(request.POST)
            if not edit_form.is_valid():
                messages.error(request, "Fix the form errors before approving.")
            else:
                entry.title = (edit_form.cleaned_data.get("title") or "").strip()
                entry.customer_edited_body = edit_form.cleaned_data["customer_edited_body"].strip()
                if not entry.effective_body_text():
                    messages.error(request, "Draft body cannot be empty.")
                else:
                    entry.save(update_fields=["title", "customer_edited_body", "updated_at"])
                    try:
                        if not entry.wordpress_post_id:
                            create_wp_draft_for_entry(entry)
                            entry.refresh_from_db()
                        if not entry.wordpress_post_id:
                            raise ValueError(
                                "WordPress draft is missing. Set WORDPRESS_URL, WORDPRESS_USERNAME, and "
                                "WORDPRESS_APPLICATION_PASSWORD in .env (e.g. for pvmehta.com)."
                            )
                        wordpress_xmlrpc.promote_draft_to_publish(post_id=entry.wordpress_post_id)
                    except Exception as exc:
                        entry.publish_error = str(exc)
                        entry.save(update_fields=["publish_error", "updated_at"])
                        messages.error(request, str(exc))
                    else:
                        entry.approval_status = BlogEntry.ApprovalStatus.PUBLISHED
                        entry.wordpress_status = "publish"
                        entry.publish_secret_token = ""
                        entry.publish_error = ""
                        entry.save(
                            update_fields=[
                                "approval_status",
                                "wordpress_status",
                                "publish_secret_token",
                                "publish_error",
                                "updated_at",
                            ]
                        )
                        messages.success(
                            request,
                            "Published on your WordPress site.",
                        )
                        return redirect("customer_entry_detail", pk=entry.pk)
    preview_html = blog_body_to_html(entry.effective_body_text())
    return render(
        request,
        "blog/site/entry_customer.html",
        {
            "entry": entry,
            "edit_form": edit_form,
            "preview_html": preview_html,
            "profile": profile,
        },
    )
