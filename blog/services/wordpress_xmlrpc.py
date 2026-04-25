"""
WordPress XML-RPC publish (logic copied from post_to_wordpress_xmlrpc.py).

Same env vars: WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_APPLICATION_PASSWORD.

Post categories: resolves a name via wp.getCategories and sends post_category (IDs) on wp.newPost
for post_type=post (WordPress ignores categories on pages).
"""
from __future__ import annotations

import html
import os
import xmlrpc.client
from typing import Any


def xmlrpc_endpoint(base_url: str) -> str:
    return base_url.rstrip("/") + "/xmlrpc.php"


def _fetch_categories(
    proxy: xmlrpc.client.ServerProxy,
    blog_id: int,
    user: str,
    password: str,
) -> list[dict[str, Any]]:
    try:
        raw = proxy.wp.getCategories(blog_id, user, password)
    except xmlrpc.client.Fault as e:
        raise RuntimeError(f"XML-RPC wp.getCategories fault {e.faultCode}: {e.faultString}") from e
    return list(raw) if raw else []


def resolve_category_id(categories: list[dict[str, Any]], wanted: str) -> int | None:
    """Match WordPress category by display name (case-insensitive, HTML-unescaped)."""
    target = html.unescape(wanted).strip().casefold()
    if not target:
        return None
    for cat in categories:
        name = html.unescape(str(cat.get("categoryName", ""))).strip().casefold()
        if name == target:
            return int(cat["categoryId"])
    # prefix / contains fallback (first match)
    for cat in categories:
        name = html.unescape(str(cat.get("categoryName", ""))).strip().casefold()
        if name and (name in target or target in name):
            return int(cat["categoryId"])
    return None


def publish_via_xmlrpc(
    *,
    title: str,
    content: str,
    post_type: str = "post",
    status: str = "draft",
    category_name: str | None = None,
    base_url: str | None = None,
    username: str | None = None,
    app_password: str | None = None,
) -> dict[str, Any]:
    base = (base_url or os.environ.get("WORDPRESS_URL", "")).strip()
    user = (username or os.environ.get("WORDPRESS_USERNAME", "")).strip()
    password = (app_password or os.environ.get("WORDPRESS_APPLICATION_PASSWORD", "")).replace(
        " ", ""
    ).strip()

    if not base or not user or not password:
        raise ValueError(
            "WORDPRESS_URL, WORDPRESS_USERNAME, and WORDPRESS_APPLICATION_PASSWORD are required."
        )

    url = xmlrpc_endpoint(base)
    proxy = xmlrpc.client.ServerProxy(url, allow_none=True)

    try:
        blogs = proxy.wp.getUsersBlogs(user, password)
    except xmlrpc.client.Fault as e:
        raise RuntimeError(f"XML-RPC wp.getUsersBlogs fault {e.faultCode}: {e.faultString}") from e
    except OSError as e:
        raise RuntimeError(f"Cannot reach {url}: {e}") from e

    if not blogs:
        raise RuntimeError("wp.getUsersBlogs returned no blogs for this user.")

    blog_id = int(blogs[0]["blogid"])
    struct: dict[str, Any] = {
        "post_title": title,
        "post_content": content,
        "post_status": status,
        "post_type": post_type,
    }

    if post_type == "post":
        cat_label = (category_name or "").strip()
        if cat_label:
            categories = _fetch_categories(proxy, blog_id, user, password)
            cid = resolve_category_id(categories, cat_label)
            if cid is None:
                names = [
                    html.unescape(str(c.get("categoryName", ""))).strip()
                    for c in categories[:30]
                    if c.get("categoryName")
                ]
                hint = ", ".join(names) if names else "(no categories returned)"
                raise RuntimeError(
                    f"No WordPress category matched {cat_label!r}. "
                    f"Create it under Posts → Categories or pick one of: {hint}"
                )
            struct["post_category"] = [cid]

    try:
        post_id = proxy.wp.newPost(blog_id, user, password, struct)
    except xmlrpc.client.Fault as e:
        raise RuntimeError(f"XML-RPC wp.newPost fault {e.faultCode}: {e.faultString}") from e

    return {
        "wordpress_post_id": int(post_id),
        "post_type": post_type,
        "status": status,
        "category_id": struct.get("post_category", [None])[0] if post_type == "post" else None,
    }


def promote_draft_to_publish(
    *,
    post_id: int,
    base_url: str | None = None,
    username: str | None = None,
    app_password: str | None = None,
) -> None:
    """Set an existing WordPress post to publish via wp.editPost (XML-RPC)."""
    base = (base_url or os.environ.get("WORDPRESS_URL", "")).strip()
    user = (username or os.environ.get("WORDPRESS_USERNAME", "")).strip()
    password = (app_password or os.environ.get("WORDPRESS_APPLICATION_PASSWORD", "")).replace(
        " ", ""
    ).strip()

    if not base or not user or not password:
        raise ValueError(
            "WORDPRESS_URL, WORDPRESS_USERNAME, and WORDPRESS_APPLICATION_PASSWORD are required."
        )

    url = xmlrpc_endpoint(base)
    proxy = xmlrpc.client.ServerProxy(url, allow_none=True)

    try:
        blogs = proxy.wp.getUsersBlogs(user, password)
    except xmlrpc.client.Fault as e:
        raise RuntimeError(f"XML-RPC wp.getUsersBlogs fault {e.faultCode}: {e.faultString}") from e
    except OSError as e:
        raise RuntimeError(f"Cannot reach {url}: {e}") from e

    if not blogs:
        raise RuntimeError("wp.getUsersBlogs returned no blogs for this user.")

    blog_id = int(blogs[0]["blogid"])
    pid = int(post_id)

    try:
        proxy.wp.editPost(blog_id, user, password, pid, {"post_status": "publish"})
    except xmlrpc.client.Fault as e:
        raise RuntimeError(f"XML-RPC wp.editPost fault {e.faultCode}: {e.faultString}") from e
