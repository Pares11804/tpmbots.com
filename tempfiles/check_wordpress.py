"""
Quick connectivity check for your WordPress site (same .env as post_to_wordpress.py).

1. GET /wp-json/ — site reachable and REST API exposed (no login).
2. If WORDPRESS_USERNAME + WORDPRESS_APPLICATION_PASSWORD are set — GET /wp-json/wp/v2/users/me
   to verify application-password auth.

If /wp-json/wp/v2/users/me returns rest_not_logged_in but XML-RPC (--xmlrpc) works, your password is
fine: the host is not passing HTTP Basic auth (Authorization header) to PHP. REST Application Passwords
need that header. Fix the server, or use post_to_wordpress_xmlrpc.py instead.

Apache/LiteSpeed (.htaccess, inside IfModule mod_rewrite.c after RewriteEngine On):

  RewriteCond %{HTTP:Authorization} .+
  RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]

nginx (PHP-FPM): pass fastcgi_param HTTP_AUTHORIZATION $http_authorization;

If REST auth works but creating posts returns rest_cannot_create, try default theme, mu-plugins off,
or probe with --probe-create.

Usage:
  python check_wordpress.py
  python check_wordpress.py --timeout 20
  python check_wordpress.py --diagnose   # show user id, slug, roles (debug rest_cannot_create)
  python check_wordpress.py --probe-create   # try creating then deleting a draft post & page (needs .env auth)
  python check_wordpress.py --xmlrpc         # wp.getUsersBlogs via xmlrpc.php (bypasses REST)
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx
from dotenv import load_dotenv


def run_xmlrpc_probe(base: str, user: str, app_pw: str) -> int:
    import xmlrpc.client

    url = base.rstrip("/") + "/xmlrpc.php"
    pwd = app_pw.replace(" ", "")
    proxy = xmlrpc.client.ServerProxy(url, allow_none=True)
    try:
        blogs = proxy.wp.getUsersBlogs(user, pwd)
    except xmlrpc.client.Fault as e:
        print(f"XML-RPC fault {e.faultCode}: {e.faultString}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Cannot reach {url}: {e}", file=sys.stderr)
        return 1
    if not blogs:
        print("wp.getUsersBlogs returned no blogs.", file=sys.stderr)
        return 1
    bid = blogs[0].get("blogid")
    print(f"OK: XML-RPC — {len(blogs)} blog(s), first blogid={bid} ({blogs[0].get('blogName', '')})")
    return 0


def run_probe_create(base: str, user: str, app_pw: str, timeout: float) -> None:
    """Try POST draft to posts and pages; delete on success. Helps spot post-only REST blocks."""
    auth = (user, app_pw.replace(" ", ""))
    payload = {
        "title": "[REST probe — safe to delete]",
        "content": "<p>Connectivity probe from check_wordpress.py</p>",
        "status": "draft",
    }
    headers = {"Accept": "application/json"}

    for label, path in (("post", "posts"), ("page", "pages")):
        url = f"{base}/wp-json/wp/v2/{path}"
        try:
            r = httpx.post(url, json=payload, auth=auth, headers=headers, timeout=timeout)
        except httpx.RequestError as e:
            print(f"  POST /{path}: request failed: {e}", file=sys.stderr)
            continue
        print(f"  POST /{path}: HTTP {r.status_code}")
        if r.status_code in (200, 201):
            try:
                pid = r.json().get("id")
            except Exception:
                pid = None
            if pid is not None:
                del_url = f"{base}/wp-json/wp/v2/{path}/{pid}"
                d = httpx.delete(
                    del_url,
                    auth=auth,
                    params={"force": "true"},
                    headers=headers,
                    timeout=timeout,
                )
                print(f"    created id={pid}, cleanup DELETE: HTTP {d.status_code}")
            continue
        try:
            err = r.json()
            print(f"    {err.get('code', '')}: {err.get('message', r.text[:300])}")
        except Exception:
            print(f"    body: {r.text[:300]}")

    print()
    print(
        "If posts fail but pages work, something targets the post type (plugin/theme). "
        "If both fail with rest_cannot_create but roles look like admin/editor, "
        "see Apache/LiteSpeed note in check_wordpress.py docstring."
    )


def main() -> int:
    load_dotenv()
    base = os.getenv("WORDPRESS_URL", "").strip().rstrip("/")
    user = os.getenv("WORDPRESS_USERNAME", "").strip()
    app_pw = os.getenv("WORDPRESS_APPLICATION_PASSWORD", "").replace(" ", "").strip()

    parser = argparse.ArgumentParser(description="Check WordPress site and REST API reachability.")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="After auth, print user id/slug/roles WordPress assigns (use if post create returns rest_cannot_create)",
    )
    parser.add_argument(
        "--probe-create",
        action="store_true",
        help="After auth, try creating & deleting a draft post and draft page (REST write test)",
    )
    parser.add_argument(
        "--xmlrpc",
        action="store_true",
        help="Call wp.getUsersBlogs on xmlrpc.php (uses password in XML body, not REST Basic auth)",
    )
    args = parser.parse_args()
    timeout = args.timeout

    if not base:
        print("WORDPRESS_URL is not set in .env", file=sys.stderr)
        return 1

    try:
        r = httpx.get(f"{base}/wp-json/", follow_redirects=True, timeout=timeout)
    except httpx.RequestError as e:
        print(f"Cannot reach site: {e}", file=sys.stderr)
        return 1

    if r.status_code != 200:
        print(f"REST index returned HTTP {r.status_code} (expected 200)", file=sys.stderr)
        return 1

    try:
        data = r.json()
    except Exception:
        print("REST index returned non-JSON", file=sys.stderr)
        return 1

    name = data.get("name", "")
    print(f"OK: {base} responds (REST API index HTTP 200)")
    if name:
        print(f"    Site name from API: {name}")

    xmlrpc_ok = False
    if args.xmlrpc:
        if not user or not app_pw:
            print("--xmlrpc requires WORDPRESS_USERNAME and WORDPRESS_APPLICATION_PASSWORD", file=sys.stderr)
            return 1
        print()
        print("--- XML-RPC (xmlrpc.php) ---")
        xr = run_xmlrpc_probe(base, user, app_pw)
        if xr != 0:
            return xr
        xmlrpc_ok = True

    if user and app_pw:
        try:
            me = httpx.get(
                f"{base}/wp-json/wp/v2/users/me",
                auth=(user, app_pw),
                follow_redirects=True,
                timeout=timeout,
            )
        except httpx.RequestError as e:
            print(f"Auth check request failed: {e}", file=sys.stderr)
            return 1
        if me.status_code != 200:
            print(
                f"Auth check failed: HTTP {me.status_code} {me.text[:200]}",
                file=sys.stderr,
            )
            try:
                err = me.json()
                wp_code = err.get("code", "")
            except Exception:
                wp_code = ""
            if wp_code == "rest_not_logged_in":
                print("", file=sys.stderr)
                print(
                    "Diagnosis: REST never saw your login. Application Passwords use the HTTP "
                    '"Authorization: Basic …" header; many hosts drop it before PHP runs.',
                    file=sys.stderr,
                )
                print(
                    "XML-RPC worked above because the password is inside the XML body, not that header.",
                    file=sys.stderr,
                )
                print("", file=sys.stderr)
                print(
                    "Options: (1) Add the .htaccess or nginx rule in this file’s top docstring; "
                    "or (2) Post with:  python post_to_wordpress_xmlrpc.py --title ... --content ...",
                    file=sys.stderr,
                )
                if not xmlrpc_ok:
                    print(
                        "(Run with --xmlrpc to confirm password works via XML-RPC.)",
                        file=sys.stderr,
                    )
            return 1
        try:
            profile = me.json()
        except Exception:
            print("Auth check: HTTP 200 but body was not valid JSON", file=sys.stderr)
            return 1
        slug = profile.get("slug", "")
        print(f"OK: application password accepted (user slug: {slug or profile.get('name', '?')})")
        roles = profile.get("roles")
        if args.diagnose:
            print()
            print("--- Diagnose: who the REST API sees for your application password ---")
            print(f"  WORDPRESS_URL: {base}")
            print(f"  WORDPRESS_USERNAME (in .env): {user!r}")
            print(f"  REST user id: {profile.get('id')}")
            print(f"  REST slug: {profile.get('slug')!r}")
            print(f"  REST name: {profile.get('name')!r}")
            print(f"  REST roles: {roles}")
            if not roles:
                print("  WARNING: empty roles — often wrong login or broken auth header on the server.", file=sys.stderr)
            elif "administrator" not in roles and "editor" not in roles:
                print(
                    "  This account is NOT administrator/editor in REST. "
                    "Fix role for THIS user (id/slug above), or fix .env username to match the user you promoted.",
                    file=sys.stderr,
                )
            cap_keys = [k for k in profile if "cap" in k.lower()]
            if cap_keys:
                print(f"  Extra fields: {cap_keys}")
            print()
            print("Raw JSON (trimmed):")
            keep = {k: profile[k] for k in ("id", "name", "slug", "roles", "url", "link") if k in profile}
            print(json.dumps(keep, indent=2))

            me_edit = httpx.get(
                f"{base}/wp-json/wp/v2/users/me",
                params={"context": "edit"},
                auth=(user, app_pw.replace(" ", "")),
                follow_redirects=True,
                timeout=timeout,
            )
            if me_edit.status_code == 200:
                try:
                    ed = me_edit.json()
                except Exception:
                    ed = {}
                caps = ed.get("capabilities")
                if caps:
                    print()
                    print("capabilities (context=edit) — create_posts / publish_posts:")
                    for k in ("create_posts", "publish_posts", "edit_posts", "edit_pages"):
                        if k in caps:
                            print(f"  {k}: {caps[k]}")
                else:
                    print()
                    print("(No 'capabilities' in context=edit response — normal on some WP versions.)")

        if args.probe_create:
            print()
            print("--- Probe: REST create (draft) then delete ---")
            run_probe_create(base, user, app_pw, timeout)
    else:
        print("    (Skipped auth: set WORDPRESS_USERNAME and WORDPRESS_APPLICATION_PASSWORD to test login)")
        if args.probe_create:
            print("--probe-create requires WORDPRESS_USERNAME and WORDPRESS_APPLICATION_PASSWORD", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
