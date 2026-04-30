"""WordPress draft creation for customer-approved posts."""

from __future__ import annotations

from django.conf import settings

from blog.models import BlogEntry
from blog.services import wordpress_xmlrpc
from blog.utils import blog_body_to_html


def create_wp_draft_for_entry(entry: BlogEntry) -> None:
    title = (entry.title or "Blog post").strip() or "Blog post"
    raw = entry.effective_body_text()
    if not raw:
        raise ValueError("No body text to publish.")
    content_html = blog_body_to_html(raw)
    wp_base = (settings.WORDPRESS_URL or "").strip().rstrip("/")
    if not wp_base:
        raise ValueError("WORDPRESS_URL is not configured.")
    cat = (entry.wordpress_category_name or "").strip() or (
        getattr(settings, "WORDPRESS_DEFAULT_CATEGORY", "") or ""
    ).strip()
    cat_for_rpc = cat or None
    result = wordpress_xmlrpc.publish_via_xmlrpc(
        title=title,
        content=content_html or raw,
        post_type="post",
        status="draft",
        category_name=cat_for_rpc,
    )
    entry.wordpress_post_id = result["wordpress_post_id"]
    entry.wordpress_post_type = "post"
    entry.wordpress_status = "draft"
    entry.generated_body = raw
    entry.save(
        update_fields=[
            "wordpress_post_id",
            "wordpress_post_type",
            "wordpress_status",
            "generated_body",
            "updated_at",
        ]
    )
