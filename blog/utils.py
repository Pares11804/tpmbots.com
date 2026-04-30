"""Helpers for turning Mistral output into HTML for preview and WordPress."""

from __future__ import annotations

from blog.wp_typography import wordpress_article_html


def blog_body_to_html(raw: str) -> str:
    """Markdown → HTML with typography (Literata / IBM Plex, inline styles) for WP and in-app preview."""
    return wordpress_article_html(raw, include_font_links=True)
