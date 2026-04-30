"""
Publish to WordPress using the legacy XML-RPC endpoint (xmlrpc.php).

Why use this instead of the REST API?
    WordPress Application Passwords over REST rely on the HTTP ``Authorization:
    Basic …`` header. Many hosts (Apache/CGI/LiteSpeed) strip that header before PHP
    runs, so REST calls fail with ``rest_not_logged_in``. XML-RPC sends the same
    application password inside the XML payload, so it often still works.

Environment (.env), same as REST tooling:
    WORDPRESS_URL — Site base URL (e.g. https://example.com)
    WORDPRESS_USERNAME — WordPress login username
    WORDPRESS_APPLICATION_PASSWORD — Application password from Users → Profile

Requirements:
    XML-RPC must be enabled (some security setups disable xmlrpc.php).

CLI examples:
    python post_to_wordpress_xmlrpc.py --title "Hello" --content "<p>Hi</p>" --status draft
    python post_to_wordpress_xmlrpc.py --title "Page" --content-file body.html --type page --status publish

WordPress XML-RPC methods used:
    wp.getUsersBlogs — Resolves ``blog_id`` (needed for multisite; single-site is typically 1).
    wp.newPost — Creates the post or page from a content struct.
"""

from __future__ import annotations

import argparse
import os
import sys
import xmlrpc.client
from pathlib import Path

from dotenv import load_dotenv


def _xmlrpc_url(base: str) -> str:
    """WordPress exposes one XML-RPC endpoint at the site root."""
    return base.rstrip("/") + "/xmlrpc.php"


def main() -> int:
    load_dotenv()
    base_url = os.getenv("WORDPRESS_URL", "").strip()
    username = os.getenv("WORDPRESS_USERNAME", "").strip()
    # Spaces in generated app passwords are cosmetic; XML-RPC accepts the compact form.
    app_password = os.getenv("WORDPRESS_APPLICATION_PASSWORD", "").replace(" ", "").strip()

    parser = argparse.ArgumentParser(
        description="Create a WordPress post or page via XML-RPC (see module docstring).",
    )
    parser.add_argument("--title", required=True, help="Post or page title")
    parser.add_argument(
        "--type",
        dest="post_type",
        choices=("post", "page"),
        default="post",
        help="Create a blog post (default) or a static page",
    )
    parser.add_argument(
        "--status",
        choices=("draft", "publish", "private", "pending"),
        default="draft",
        help="WordPress post_status value",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--content", help="HTML (or plain) body inline")
    group.add_argument(
        "--content-file",
        type=Path,
        metavar="PATH",
        help="Read body from UTF-8 file",
    )
    args = parser.parse_args()

    if not base_url or not username or not app_password:
        print("Missing WORDPRESS_URL, WORDPRESS_USERNAME, or WORDPRESS_APPLICATION_PASSWORD.", file=sys.stderr)
        return 1

    if args.content_file is not None:
        content = args.content_file.read_text(encoding="utf-8")
    else:
        content = args.content or ""

    url = _xmlrpc_url(base_url)
    # allow_none=True lets the client decode XML-RPC nil if the server sends it.
    proxy = xmlrpc.client.ServerProxy(url, allow_none=True)

    # Resolve which blog to post to (multisite has many; single install returns one row).
    try:
        blogs = proxy.wp.getUsersBlogs(username, app_password)
    except xmlrpc.client.Fault as e:
        print(f"XML-RPC wp.getUsersBlogs fault {e.faultCode}: {e.faultString}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Cannot reach {url}: {e}", file=sys.stderr)
        return 1

    if not blogs:
        print("wp.getUsersBlogs returned no blogs for this user.", file=sys.stderr)
        return 1

    blog_id = int(blogs[0]["blogid"])

    # Keys match WordPress wp.newPost content struct (see WordPress XML-RPC API docs).
    struct = {
        "post_title": args.title,
        "post_content": content,
        "post_status": args.status,
        "post_type": args.post_type,
    }

    try:
        post_id = proxy.wp.newPost(blog_id, username, app_password, struct)
    except xmlrpc.client.Fault as e:
        print(f"XML-RPC wp.newPost fault {e.faultCode}: {e.faultString}", file=sys.stderr)
        return 1

    print(f"Created {args.post_type} via XML-RPC id={post_id} status={args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
