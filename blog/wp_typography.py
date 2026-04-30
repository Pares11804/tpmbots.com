"""
Rich HTML for WordPress and in-app preview: semantic article, scoped CSS fallback,
per-element inline styles (survives KSES), Markdown Extra (tables, fenced code, etc.).
"""

from __future__ import annotations

import html
import re

import markdown
from bs4 import BeautifulSoup

# Google Fonts
GOOGLE_FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
    '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,500;1,400&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Literata:ital,opsz,wght@0,7..72,400;0,7..72,600;0,7..72,700;1,7..72,400&display=swap" rel="stylesheet" />\n'
)

ROOT_CLASS = "tpmbots-wp-content"
INNER_CLASS = "tpm-post-inner"

# Outer article: layout + base font (children inherit)
ARTICLE_STYLE = (
    "font-family: 'Literata', Georgia, 'Times New Roman', serif; "
    "font-size: 1.125rem; "
    "line-height: 1.8; "
    "color: #1a1a1a; "
    "max-width: 46rem; "
    "margin: 0 auto; "
    "padding: 0.75rem 0 2.5rem; "
    "letter-spacing: 0.01em; "
    "-webkit-font-smoothing: antialiased; "
    "text-rendering: optimizeLegibility; "
    "box-sizing: border-box;"
)

INNER_WRAPPER_STYLE = "box-sizing: border-box; min-width: 0;"

LEAD_PARAGRAPH_STYLE = (
    "font-size: 1.2rem; "
    "line-height: 1.75; "
    "color: #2d333b; "
    "margin: 0 0 1.35em; "
    "font-weight: 400;"
)

_TAG_STYLES: dict[str, str] = {
    "h1": (
        "font-family: 'Literata', Georgia, serif; font-size: 2.125rem; font-weight: 700; "
        "line-height: 1.2; margin: 0 0 0.65em; color: #0f1419; letter-spacing: -0.03em;"
    ),
    "h2": (
        "font-family: 'Literata', Georgia, serif; font-size: 1.65rem; font-weight: 700; "
        "line-height: 1.28; margin: 2em 0 0.55em; color: #121820; letter-spacing: -0.025em; "
        "border-bottom: 1px solid rgba(0,0,0,0.08); padding-bottom: 0.35em;"
    ),
    "h3": (
        "font-family: 'Literata', Georgia, serif; font-size: 1.35rem; font-weight: 600; "
        "line-height: 1.35; margin: 1.75em 0 0.5em; color: #1a2332; letter-spacing: -0.02em;"
    ),
    "h4": (
        "font-family: 'IBM Plex Sans', system-ui, sans-serif; font-size: 1.05rem; font-weight: 600; "
        "line-height: 1.4; margin: 1.5em 0 0.45em; color: #2c3544; letter-spacing: 0.02em; text-transform: uppercase;"
    ),
    "h5": (
        "font-family: 'IBM Plex Sans', system-ui, sans-serif; font-size: 0.95rem; font-weight: 600; "
        "margin: 1.25em 0 0.4em; color: #3d4a5c;"
    ),
    "h6": (
        "font-family: 'IBM Plex Sans', system-ui, sans-serif; font-size: 0.9rem; font-weight: 600; "
        "margin: 1.1em 0 0.35em; color: #5a6570; letter-spacing: 0.04em;"
    ),
    "p": "margin: 0 0 1.25em; line-height: 1.85;",
    "blockquote": (
        "margin: 1.5em 0; padding: 0.85em 1.15em 0.85em 1.35em; border-left: 4px solid #2d6a4f; "
        "background: linear-gradient(90deg, rgba(45,106,79,0.08) 0%, rgba(45,106,79,0.02) 100%); "
        "font-style: italic; color: #2a3038; border-radius: 0 8px 8px 0;"
    ),
    "ul": "margin: 0 0 1.25em 1.15em; padding-left: 0.35em; list-style-type: disc;",
    "ol": "margin: 0 0 1.25em 1.15em; padding-left: 0.35em; list-style-type: decimal;",
    "li": "margin: 0.4em 0; line-height: 1.75; padding-left: 0.2em;",
    "a": "color: #1d6b4a; text-decoration: underline; text-underline-offset: 3px; font-weight: 500;",
    "strong": "font-weight: 700; color: #0f1419;",
    "em": "font-style: italic;",
    "code": (
        "font-family: 'IBM Plex Mono', 'Consolas', 'Monaco', monospace; font-size: 0.88em; "
        "background: rgba(0,0,0,0.06); padding: 0.15em 0.45em; border-radius: 4px; color: #1a1a1a;"
    ),
    "pre": (
        "font-family: 'IBM Plex Mono', 'Consolas', monospace; font-size: 0.875rem; line-height: 1.58; "
        "background: #f0f2f5; border: 1px solid rgba(0,0,0,0.1); border-radius: 10px; "
        "padding: 1.1rem 1.25rem; overflow-x: auto; margin: 1.35em 0; color: #1e2430; "
        "box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);"
    ),
    "hr": "border: none; border-top: 1px solid rgba(0,0,0,0.12); margin: 2.75em 0;",
    "table": (
        "width: 100%; border-collapse: collapse; margin: 1.85em 0; font-size: 0.95em; "
        "font-family: 'IBM Plex Sans', system-ui, sans-serif; box-shadow: 0 1px 3px rgba(0,0,0,0.06); "
        "border-radius: 8px; overflow: hidden;"
    ),
    "thead": "background: linear-gradient(180deg, rgba(0,0,0,0.05) 0%, rgba(0,0,0,0.02) 100%);",
    "th": (
        "text-align: left; padding: 0.7em 0.9em; border: 1px solid rgba(0,0,0,0.1); "
        "font-weight: 600; color: #1a2332;"
    ),
    "td": "padding: 0.65em 0.9em; border: 1px solid rgba(0,0,0,0.08); vertical-align: top;",
    "tr": "",
    "img": "max-width: 100%; height: auto; border-radius: 8px; margin: 1.15em 0; box-shadow: 0 4px 14px rgba(0,0,0,0.08);",
    "figcaption": (
        "font-family: 'IBM Plex Sans', system-ui, sans-serif; font-size: 0.85rem; color: #5a6570; "
        "margin-top: 0.35em; font-style: italic;"
    ),
    "figure": "margin: 1.5em 0;",
}


def _merge_style(existing: str | None, add: str) -> str:
    ex = (existing or "").strip().rstrip(";")
    ad = add.strip().rstrip(";")
    if not ex:
        return ad
    if not ad:
        return ex
    return f"{ex}; {ad}"


def _normalize_raw_markdown(text: str) -> str:
    """Unify line endings and collapse runaway blank lines (common in LLM output)."""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"\n{4,}", "\n\n\n", t)
    return t.strip()


def _build_scoped_style_block() -> str:
    """Fallback if theme allows <style> in post content (inline styles still applied)."""
    rules: list[str] = [
        f".{ROOT_CLASS}.{ROOT_CLASS} {{ {ARTICLE_STYLE} }}",
        f".{ROOT_CLASS} .{INNER_CLASS} {{ {INNER_WRAPPER_STYLE} }}",
    ]
    for tag, decl in _TAG_STYLES.items():
        if not decl.strip():
            continue
        sel = f".{ROOT_CLASS} .{INNER_CLASS} {tag}"
        rules.append(f"{sel} {{ {decl} }}")
    rules.append(
        f".{ROOT_CLASS} .{INNER_CLASS} p.tpm-lead {{ {LEAD_PARAGRAPH_STYLE} }}"
    )
    css = "\n".join(rules)
    return f'<style type="text/css">\n{css}\n</style>\n'


def _apply_tag_styles(root) -> None:
    for tag in root.find_all(True):
        name = tag.name.lower() if tag.name else ""
        if name in ("script", "style", "link"):
            continue
        extra = _TAG_STYLES.get(name)
        if not extra:
            continue
        tag["style"] = _merge_style(tag.get("style"), extra)


def _striping_table_rows(root) -> None:
    for tbody in root.find_all("tbody"):
        for i, tr in enumerate(tbody.find_all("tr", recursive=False)):
            if i % 2 == 1:
                tr["style"] = _merge_style(
                    tr.get("style"),
                    "background: rgba(0,0,0,0.025);",
                )
    # Tables without tbody (simple MD)
    for table in root.find_all("table"):
        if table.find("tbody") is None:
            rows = table.find_all("tr")
            for i, tr in enumerate(rows):
                if i > 0 and i % 2 == 1:
                    tr["style"] = _merge_style(
                        tr.get("style"),
                        "background: rgba(0,0,0,0.025);",
                    )


def _style_lead_paragraph(root) -> None:
    """First body paragraph (not inside quote/code) gets lead typography."""
    for p in root.find_all("p"):
        if p.find_parent(["blockquote", "pre", "li", "td", "th"]):
            continue
        p["class"] = _merge_class(p.get("class"), "tpm-lead")
        p["style"] = _merge_style(p.get("style"), LEAD_PARAGRAPH_STYLE)
        break


def _merge_class(existing, add: str) -> list[str]:
    if existing is None:
        return [add]
    if isinstance(existing, str):
        parts = [p for p in existing.split() if p]
    else:
        parts = list(existing)
    if add not in parts:
        parts.append(add)
    return parts


def _fix_pre_code_children(root) -> None:
    for pre in root.find_all("pre"):
        for ch in pre.children:
            if getattr(ch, "name", None) == "code":
                ch["style"] = _merge_style(
                    ch.get("style"),
                    "background: transparent; padding: 0; border-radius: 0; font-size: inherit;",
                )


def wordpress_article_html(raw: str, *, include_font_links: bool = True) -> str:
    """
    Markdown (Extra) → semantic HTML with inline + scoped CSS for WordPress.
    """
    text = _normalize_raw_markdown(raw or "")
    if not text:
        return ""

    try:
        inner_html = markdown.markdown(
            text,
            extensions=["extra", "smarty", "sane_lists"],
            output_format="html",
        )
    except Exception:
        inner_html = f"<pre>{html.escape(raw or '')}</pre>"

    fragment = (
        f'<article class="{ROOT_CLASS}" style="{ARTICLE_STYLE}" role="article" '
        f'itemscope itemtype="https://schema.org/BlogPosting">'
        f'<div class="{INNER_CLASS}" style="{INNER_WRAPPER_STYLE}">{inner_html}</div>'
        f"</article>"
    )
    soup = BeautifulSoup(fragment, "html.parser")
    root = soup.find("article", class_=ROOT_CLASS)
    inner = soup.find("div", class_=INNER_CLASS)
    if not root or not inner:
        return inner_html

    _apply_tag_styles(inner)
    _style_lead_paragraph(inner)
    _striping_table_rows(inner)
    _fix_pre_code_children(inner)

    parts: list[str] = []
    if include_font_links:
        parts.append(GOOGLE_FONTS_LINK)
    parts.append(_build_scoped_style_block())
    parts.append(str(root))
    return "".join(parts)


def strip_wp_typography_for_plain_preview(html: str) -> str:
    if not html:
        return ""
    s = BeautifulSoup(html, "html.parser")
    art = s.find("article", class_=ROOT_CLASS)
    if art:
        inner = art.find("div", class_=INNER_CLASS)
        if inner:
            return inner.get_text("\n", strip=True)
        return art.get_text("\n", strip=True)
    div = s.find("div", class_=ROOT_CLASS)
    return div.get_text("\n", strip=True) if div else html
