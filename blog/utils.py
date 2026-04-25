"""Helpers for turning Mistral output into HTML for preview and WordPress."""

from __future__ import annotations

import html

import markdown


def blog_body_to_html(raw: str) -> str:
    """Convert Markdown-style Mistral output to HTML for preview and wp.newPost."""
    text = raw or ""
    if not text.strip():
        return ""
    try:
        return markdown.markdown(
            text,
            extensions=["nl2br", "fenced_code", "tables"],
            output_format="html",
        )
    except Exception:
        return f"<pre>{html.escape(text)}</pre>"
