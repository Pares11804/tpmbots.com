"""
Django settings for mistral_wp_site.

Loads sibling-repo .env from ../.env (parent of mistral_wp_django) when present.
PostgreSQL via PG* or DATABASE_URL-style env vars.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Repo root: mistral-ai-testing/ (contains generate_blog_entry.py, .env)
REPO_ROOT = BASE_DIR.parent
load_dotenv(REPO_ROOT / ".env")
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-me-in-production-use-env-DJANGO_SECRET_KEY",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "blog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mistral_wp_site.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mistral_wp_site.wsgi.application"

# --- PostgreSQL (env: PGDATABASE, PGUSER, PGPASSWORD, PGHOST, PGPORT) ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("PGDATABASE", "mistraldb"),
        "USER": os.environ.get("PGUSER", "mistraldbuser"),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", "localhost"),
        "PORT": os.environ.get("PGPORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    p for p in (BASE_DIR / "images", BASE_DIR / "imaes") if p.exists()
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# --- Email (draft notifications + publish link) ---
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "").strip()
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
# Gmail: use EITHER (TLS+587) OR (SSL+465), never both True — "Connection unexpectedly closed" often means a mismatch here.
_email_use_tls = os.environ.get("EMAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
_email_use_ssl = os.environ.get("EMAIL_USE_SSL", "false").lower() in ("1", "true", "yes")
if _email_use_tls and _email_use_ssl:
    raise ValueError("Set only one of EMAIL_USE_TLS or EMAIL_USE_SSL to true (see env.example).")
EMAIL_USE_TLS = _email_use_tls
EMAIL_USE_SSL = _email_use_ssl
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip()
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").strip()
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "60"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "webmaster@localhost")
NOTIFICATION_EMAIL = os.environ.get("NOTIFICATION_EMAIL", "vaatrak@gmail.com")
# Base URL for links in emails (no trailing slash), e.g. http://127.0.0.1:8000 or https://your-domain.com
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
# When true, customer draft-review email is sent as soon as they submit (testing).
# Set IMMEDIATE_CUSTOMER_DRAFT_EMAIL=false in production to use draft_lead_hours + cron only.
IMMEDIATE_CUSTOMER_DRAFT_EMAIL = os.environ.get(
    "IMMEDIATE_CUSTOMER_DRAFT_EMAIL", "true"
).lower() in ("1", "true", "yes")
# Optional default WP category when the form leaves category blank
WORDPRESS_DEFAULT_CATEGORY = os.environ.get("WORDPRESS_DEFAULT_CATEGORY", "").strip()
WORDPRESS_URL = os.environ.get("WORDPRESS_URL", "").strip()
