from django import forms

from blog.services.mistral_service import DEFAULT_ORACLE_SCRIPT
from blog.wordpress_categories import WORDPRESS_CATEGORY_CHOICES


class GenerateBlogForm(forms.Form):
    oracle_script = forms.CharField(
        label="Your script",
        widget=forms.Textarea(
            attrs={
                "rows": 22,
                "cols": 100,
                "placeholder": "Paste your Oracle (or other) script here…",
            }
        ),
        initial=DEFAULT_ORACLE_SCRIPT.strip(),
        help_text=(
            "Submit once: Mistral writes the post, a draft is created on WordPress, "
            "and you get an email with links to review and to publish."
        ),
    )
    post_title = forms.CharField(
        label="Post title (optional)",
        max_length=500,
        required=False,
        help_text="If empty, a title like “Draft — 2026-04-08 12:00 UTC” is used.",
    )
    wordpress_category_name = forms.ChoiceField(
        label="WordPress category",
        choices=WORDPRESS_CATEGORY_CHOICES,
        required=False,
        help_text="Pick a category from your site list, or leave “Optional” and use WORDPRESS_DEFAULT_CATEGORY in .env.",
    )
