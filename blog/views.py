from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from blog.email_notifications import send_draft_created_email
from blog.forms import GenerateBlogForm
from blog.models import BlogEntry
from blog.services import mistral_service, wordpress_xmlrpc
from blog.utils import blog_body_to_html


def entry_list(request: HttpRequest) -> HttpResponse:
    entries = BlogEntry.objects.all()[:100]
    return render(request, "blog/entry_list.html", {"entries": entries})


def entry_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = GenerateBlogForm(request.POST)
        if form.is_valid():
            script = form.cleaned_data["oracle_script"]
            model = mistral_service.DEFAULT_MISTRAL_MODEL
            wp_base = (settings.WORDPRESS_URL or "").strip().rstrip("/")

            title = (form.cleaned_data.get("post_title") or "").strip()
            if not title:
                title = f"Draft — {timezone.now():%Y-%m-%d %H:%M} UTC"

            cat = (form.cleaned_data.get("wordpress_category_name") or "").strip()
            if not cat:
                cat = (getattr(settings, "WORDPRESS_DEFAULT_CATEGORY", "") or "").strip()
            cat_for_rpc = cat or None

            try:
                body = mistral_service.generate_blog_from_oracle_script(script, model=model)
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Mistral error: {e}")
            else:
                content_html = blog_body_to_html(body)
                if not wp_base:
                    messages.error(
                        request,
                        "Set WORDPRESS_URL in .env (e.g. https://pvmehta.com). Draft was not created on WordPress.",
                    )
                    BlogEntry.objects.create(
                        oracle_script=script,
                        generated_body=body,
                        title=title,
                        mistral_model=model,
                        wordpress_category_name=cat,
                        publish_error="WORDPRESS_URL missing",
                    )
                    return render(request, "blog/entry_form.html", {"form": form})

                try:
                    result = wordpress_xmlrpc.publish_via_xmlrpc(
                        title=title,
                        content=content_html or body,
                        post_type="post",
                        status="draft",
                        category_name=cat_for_rpc,
                    )
                except (ValueError, RuntimeError) as e:
                    BlogEntry.objects.create(
                        oracle_script=script,
                        generated_body=body,
                        title=title,
                        mistral_model=model,
                        wordpress_category_name=cat,
                        publish_error=str(e),
                    )
                    messages.error(request, f"WordPress draft failed: {e}")
                    return render(request, "blog/entry_form.html", {"form": form})

                secret = secrets.token_urlsafe(32)
                entry = BlogEntry.objects.create(
                    oracle_script=script,
                    generated_body=body,
                    title=title,
                    mistral_model=model,
                    wordpress_category_name=cat,
                    wordpress_post_id=result["wordpress_post_id"],
                    wordpress_post_type="post",
                    wordpress_status="draft",
                    publish_secret_token=secret,
                    publish_error="",
                )

                site = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
                publish_url = f"{site}/publish/{entry.pk}/{secret}/"
                admin_url = f"{wp_base}/wp-admin/post.php?post={entry.wordpress_post_id}&action=edit"
                public_url = f"{wp_base}/?p={entry.wordpress_post_id}"

                email_err = ""
                try:
                    send_draft_created_email(
                        entry=entry,
                        admin_edit_url=admin_url,
                        one_click_publish_url=publish_url,
                        public_preview_url=public_url,
                    )
                except Exception as exc:
                    email_err = str(exc)
                    entry.email_notify_error = email_err
                    entry.save(update_fields=["email_notify_error", "updated_at"])

                return render(
                    request,
                    "blog/entry_done.html",
                    {
                        "entry": entry,
                        "admin_url": admin_url,
                        "publish_url": publish_url,
                        "public_url": public_url,
                        "email_error": email_err,
                    },
                )
    else:
        form = GenerateBlogForm()
    return render(request, "blog/entry_form.html", {"form": form})


def publish_entry(request: HttpRequest, pk: int, token: str) -> HttpResponse:
    entry = get_object_or_404(BlogEntry, pk=pk)
    if not entry.publish_secret_token or not secrets.compare_digest(
        entry.publish_secret_token, token
    ):
        return HttpResponseForbidden(
            "This publish link is invalid, already used, or expired. "
            "Publish from WordPress admin if you still have a draft."
        )
    if not entry.wordpress_post_id:
        return HttpResponseForbidden("No WordPress post is associated with this entry.")

    try:
        wordpress_xmlrpc.promote_draft_to_publish(post_id=entry.wordpress_post_id)
    except (ValueError, RuntimeError) as e:
        return render(
            request,
            "blog/publish_result.html",
            {"ok": False, "message": str(e), "entry": entry},
            status=500,
        )

    entry.publish_secret_token = ""
    entry.wordpress_status = "publish"
    entry.publish_error = ""
    entry.save(
        update_fields=[
            "publish_secret_token",
            "wordpress_status",
            "publish_error",
            "updated_at",
        ]
    )
    wp_base = (settings.WORDPRESS_URL or "").strip().rstrip("/")
    live_url = f"{wp_base}/?p={entry.wordpress_post_id}" if wp_base else ""
    return render(
        request,
        "blog/publish_result.html",
        {
            "ok": True,
            "message": "Post is now published on WordPress.",
            "entry": entry,
            "live_url": live_url,
        },
    )


def entry_detail(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(BlogEntry, pk=pk)
    wordpress_url = (settings.WORDPRESS_URL or "").strip().rstrip("/")
    preview_html = blog_body_to_html(entry.generated_body)

    wp_admin_url = ""
    public_url = ""
    if wordpress_url and entry.wordpress_post_id:
        wp_admin_url = f"{wordpress_url}/wp-admin/post.php?post={entry.wordpress_post_id}&action=edit"
        public_url = f"{wordpress_url}/?p={entry.wordpress_post_id}"

    site = getattr(settings, "SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    publish_url = ""
    if entry.publish_secret_token:
        publish_url = f"{site}/publish/{entry.pk}/{entry.publish_secret_token}/"

    return render(
        request,
        "blog/entry_detail.html",
        {
            "entry": entry,
            "wordpress_url": wordpress_url,
            "preview_html": preview_html,
            "wp_admin_url": wp_admin_url,
            "public_url": public_url,
            "publish_url": publish_url,
        },
    )
