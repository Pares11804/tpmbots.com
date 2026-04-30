from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User

from blog.models import CustomerProfile, SubscriptionTier

WEEKDAY_CHOICES = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]

# Curated IANA zones (expand as needed)
COMMON_TIMEZONES = [
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "America/Toronto",
    "America/Mexico_City",
    "America/Sao_Paulo",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Madrid",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Singapore",
    "Asia/Tokyo",
    "Asia/Seoul",
    "Australia/Sydney",
    "Pacific/Auckland",
]
TIMEZONE_CHOICES = [(z, z.replace("_", " ")) for z in COMMON_TIMEZONES]


class EmailLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget.attrs.setdefault("autocomplete", "username")
        self.fields["password"].widget.attrs.setdefault("autocomplete", "current-password")


class RegistrationForm(forms.Form):
    email = forms.EmailField()
    password1 = forms.CharField(
        widget=forms.PasswordInput,
        min_length=10,
        label="Password",
        help_text="Use at least 10 characters.",
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput,
        min_length=10,
        label="Re-enter password",
    )
    captcha_answer = forms.CharField(
        max_length=16,
        label="CAPTCHA answer",
        widget=forms.TextInput(attrs={"placeholder": "Type the result"}),
        help_text="Solve the simple math challenge shown above.",
    )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        return cleaned

class SubscriptionSetupForm(forms.ModelForm):
    billing_setup_complete = forms.BooleanField(
        required=True,
        label="I have added a valid payment method for after my free trial",
        help_text="You will not be charged until the trial ends. Integrations such as Stripe can be wired here later.",
    )

    class Meta:
        model = CustomerProfile
        fields = (
            "tier",
            "posts_per_week",
            "publish_weekday",
            "publish_time",
            "publish_timezone",
            "draft_lead_hours",
            "billing_setup_complete",
        )
        help_texts = {
            "tier": "Choose the plan that matches how you publish.",
            "posts_per_week": "Only enabled for the custom frequency text plan.",
            "publish_weekday": "Day of the week you prefer to publish.",
            "publish_time": "Time on that day in your selected timezone.",
            "publish_timezone": "IANA timezone for your publish schedule.",
            "draft_lead_hours": "We email your draft this many hours before publish time so you can review.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publish_weekday"] = forms.TypedChoiceField(
            coerce=int,
            choices=WEEKDAY_CHOICES,
            label="Publish day",
        )
        tz_choices = list(TIMEZONE_CHOICES)
        current_tz = (getattr(self.instance, "publish_timezone", None) or "").strip()
        if current_tz and all(current_tz != c[0] for c in tz_choices):
            tz_choices.insert(0, (current_tz, f"{current_tz} (saved)"))
        self.fields["publish_timezone"] = forms.ChoiceField(
            label="Publish timezone",
            choices=tz_choices,
            help_text=self.Meta.help_texts["publish_timezone"],
        )
        self.fields["posts_per_week"].label = "Posts per week"
        self.fields["posts_per_week"].widget.attrs.update({"min": 1, "max": 14, "id": "id_posts_per_week"})
        self.fields["tier"].widget.attrs["id"] = "id_tier"

        tier_val = None
        if self.data:
            tier_val = self.data.get("tier")
        elif self.instance.pk:
            tier_val = self.instance.tier

        if tier_val != SubscriptionTier.TEXT_CUSTOM:
            self.fields["posts_per_week"].widget.attrs["readonly"] = True

    def clean_posts_per_week(self):
        tier = self.cleaned_data.get("tier")
        n = int(self.cleaned_data.get("posts_per_week") or 1)
        if tier != SubscriptionTier.TEXT_CUSTOM:
            return 1
        if n < 1:
            n = 1
        if n > 14:
            raise forms.ValidationError("Please contact us for enterprise frequency.")
        return n

    def clean(self):
        cleaned = super().clean()
        tier = cleaned.get("tier")
        if tier != SubscriptionTier.TEXT_CUSTOM:
            cleaned["posts_per_week"] = 1
        return cleaned


class CustomerBlogForm(forms.Form):
    title = forms.CharField(
        max_length=500,
        required=True,
        help_text="Used as the working title for Mistral and WordPress.",
    )
    customer_brief = forms.CharField(
        label="Draft text / notes",
        widget=forms.Textarea(
            attrs={
                "rows": 16,
                "placeholder": "Outline, bullets, or rough copy — Mistral will expand this into a full post.",
            }
        ),
        help_text="We send this to Mistral AI with your title and category to generate the blog body.",
    )
    wordpress_category_name = forms.CharField(
        label="Category",
        max_length=200,
        required=False,
        help_text="WordPress category name (must exist on your site, e.g. on pvmehta.com).",
    )


class CustomerDraftEditForm(forms.Form):
    title = forms.CharField(max_length=500, required=False)
    customer_edited_body = forms.CharField(
        label="Post body (Markdown)",
        widget=forms.Textarea(attrs={"rows": 18}),
        help_text="Edit the AI-generated post before approving. Changes here are not auto-synced to WordPress; use wp-admin for layout tweaks.",
    )
