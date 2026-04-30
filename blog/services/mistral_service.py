"""
Blog generation via Mistral (logic copied from generate_blog_entry.py).

Uses mistralai client: Mistral + chat.complete with the same system prompt and
user message shape as the standalone script.
"""
from __future__ import annotations

import os

from mistralai.client import Mistral

# Fixed model for the Django UI (no user-facing model picker).
DEFAULT_MISTRAL_MODEL = "mistral-large-latest"
# Mistral/httpx read timeout (ms). Long blog generations often exceed defaults; override via MISTRAL_TIMEOUT_MS.
_DEFAULT_TIMEOUT_MS = 300_000  # 5 minutes


def _timeout_ms() -> int:
    raw = os.environ.get("MISTRAL_TIMEOUT_MS", "").strip()
    if raw.isdigit():
        return max(30_000, int(raw))  # floor 30s
    return _DEFAULT_TIMEOUT_MS

# Default sample Oracle script (same as generate_blog_entry.py)
DEFAULT_ORACLE_SCRIPT = """
Cset lines 120 pages 200

prompt 'process started at 9:14AM on 3/18'
col sofar_gb format 9999999
col avg_gb_copy_per_min format 999999

SELECT name, value/(1024*1024*1024) sofar_GB,
       value/(1024*1024*1024) / ((sysdate - to_date('18-MAR-2026:09:14','DD-MON-RRRR:HH24:MI'))*(24*60)) avg_gb_copy_per_min
FROM v$sysstat
WHERE name IN ('physical write total bytes', 'physical write bytes');
"""


def generate_blog_from_oracle_script(
    oracle_script: str,
    *,
    api_key: str | None = None,
    model: str = DEFAULT_MISTRAL_MODEL,
) -> str:
    key = api_key or os.environ.get("MISTRAL_API_KEY")
    if not key or not str(key).strip():
        raise ValueError("MISTRAL_API_KEY is missing (env or argument).")

    timeout_ms = _timeout_ms()
    client = Mistral(api_key=key, timeout_ms=timeout_ms)
    response = client.chat.complete(
        model=model,
        timeout_ms=timeout_ms,
        messages=[
            {
                "role": "system",
                "content": "You are a technical writer specializing in Oracle Databases.",
            },
            {
                "role": "user",
                "content": f"Turn this Oracle script into a blog post: {oracle_script}",
            },
        ],
    )
    return response.choices[0].message.content or ""


def generate_blog_from_customer_brief(
    *,
    title: str,
    customer_brief: str,
    category_name: str = "",
    api_key: str | None = None,
    model: str = DEFAULT_MISTRAL_MODEL,
) -> str:
    """
    Turn customer title + notes + optional category into a full blog post (Markdown).
    """
    key = api_key or os.environ.get("MISTRAL_API_KEY")
    if not key or not str(key).strip():
        raise ValueError("MISTRAL_API_KEY is missing (env or argument).")

    cat = (category_name or "").strip()
    cat_block = f"\nPreferred WordPress category name: {cat}\n" if cat else ""

    timeout_ms = _timeout_ms()
    client = Mistral(api_key=key, timeout_ms=timeout_ms)
    response = client.chat.complete(
        model=model,
        timeout_ms=timeout_ms,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert business and technology blog writer. "
                    "Write clear, professional posts suitable for a public website. "
                    "Output MUST be valid Markdown that will convert to rich HTML: "
                    "use ## and ### section headings (at least 3 distinct sections after the intro), "
                    "unordered or numbered lists for steps or takeaways, **bold** for key terms, "
                    "and blank lines between paragraphs. "
                    "Optionally use > blockquotes for a short summary or callout, and Markdown tables when comparing options. "
                    "Do not use HTML tags in the body unless quoting code. "
                    "Do not fabricate facts; expand only from the author's notes when reasonable."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Proposed title: {title.strip() or '(untitled)'}\n\n"
                    f"Author notes / outline / source material:\n{customer_brief.strip()}\n"
                    f"{cat_block}\n"
                    "Write the full blog post body in Markdown only. "
                    "Structure: (1) opening intro as one or two paragraphs with no heading, "
                    "(2) then ## sections with ### subsections as needed, "
                    "(3) end with a brief conclusion or next steps. "
                    "If repeating the proposed title as an H1 would be redundant, start sections with ## instead of #."
                ),
            },
        ],
    )
    return response.choices[0].message.content or ""
