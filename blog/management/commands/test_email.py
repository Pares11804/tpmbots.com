"""
Diagnose Django email configuration and optionally send a test message.

Usage:
  python manage.py test_email
  python manage.py test_email --verbose   # SMTP protocol debug to stderr
  python manage.py test_email --dry-run   # Print settings only, no send
"""

from __future__ import annotations

import smtplib
import ssl
import traceback

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError


def _mask(s: str) -> str:
    if not s:
        return "(empty)"
    return f"{len(s)} characters (hidden)"


class Command(BaseCommand):
    help = "Print email-related settings (secrets masked) and send a test email."

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable smtplib debug output (raw SMTP conversation on stderr).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print configuration; do not connect or send.",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        verbose = options["verbose"]

        self.stdout.write(self.style.NOTICE("=== Django email settings ==="))
        self.stdout.write(f"EMAIL_BACKEND:     {settings.EMAIL_BACKEND}")
        self.stdout.write(f"EMAIL_HOST:        {getattr(settings, 'EMAIL_HOST', '')!r}")
        self.stdout.write(f"EMAIL_PORT:        {getattr(settings, 'EMAIL_PORT', '')}")
        self.stdout.write(f"EMAIL_USE_TLS:     {getattr(settings, 'EMAIL_USE_TLS', '')}")
        self.stdout.write(f"EMAIL_USE_SSL:     {getattr(settings, 'EMAIL_USE_SSL', '')}")
        self.stdout.write(f"EMAIL_TIMEOUT:     {getattr(settings, 'EMAIL_TIMEOUT', '')}")
        self.stdout.write(f"EMAIL_HOST_USER:   {getattr(settings, 'EMAIL_HOST_USER', '')!r}")
        pw = getattr(settings, "EMAIL_HOST_PASSWORD", "") or ""
        self.stdout.write(f"EMAIL_HOST_PASSWORD: {_mask(pw)}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL:{getattr(settings, 'DEFAULT_FROM_EMAIL', '')!r}")
        self.stdout.write(f"NOTIFICATION_EMAIL:{getattr(settings, 'NOTIFICATION_EMAIL', '')!r}")

        if settings.EMAIL_USE_TLS and settings.EMAIL_USE_SSL:
            raise CommandError("EMAIL_USE_TLS and EMAIL_USE_SSL are both True — fix .env.")

        if "console" in settings.EMAIL_BACKEND.lower():
            self.stdout.write(
                self.style.WARNING(
                    "EMAIL_BACKEND is console — emails are printed to the terminal, not delivered."
                )
            )

        if dry:
            self.stdout.write(self.style.SUCCESS("Dry run: no connection attempted."))
            return

        if not getattr(settings, "EMAIL_HOST", "").strip():
            raise CommandError("EMAIL_HOST is empty — set it in .env for SMTP.")

        to = getattr(settings, "NOTIFICATION_EMAIL", "") or ""
        if not to.strip():
            raise CommandError("NOTIFICATION_EMAIL is empty.")

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or settings.EMAIL_HOST_USER
        if not from_email:
            raise CommandError("DEFAULT_FROM_EMAIL and EMAIL_HOST_USER are both empty.")

        self.stdout.write(self.style.NOTICE("\n=== Low-level SMTP check ==="))
        try:
            if settings.EMAIL_USE_SSL:
                ctx = ssl.create_default_context()
                conn = smtplib.SMTP_SSL(
                    settings.EMAIL_HOST,
                    settings.EMAIL_PORT,
                    timeout=settings.EMAIL_TIMEOUT or 60,
                    context=ctx,
                )
            else:
                conn = smtplib.SMTP(
                    settings.EMAIL_HOST,
                    settings.EMAIL_PORT,
                    timeout=settings.EMAIL_TIMEOUT or 60,
                )
            if verbose:
                conn.set_debuglevel(1)
            if settings.EMAIL_USE_TLS and not settings.EMAIL_USE_SSL:
                conn.ehlo()
                conn.starttls(context=ssl.create_default_context())
                conn.ehlo()
            user = settings.EMAIL_HOST_USER or ""
            password = settings.EMAIL_HOST_PASSWORD or ""
            if user:
                conn.login(user, password)
            conn.quit()
            self.stdout.write(self.style.SUCCESS("SMTP connect + STARTTLS/SSL + login: OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"SMTP low-level check FAILED: {e!r}"))
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            self.stdout.write(
                self.style.WARNING(
                    "\nHints:\n"
                    "  • Gmail 587: EMAIL_USE_TLS=true, EMAIL_USE_SSL=false\n"
                    "  • Gmail 465: EMAIL_USE_TLS=false, EMAIL_USE_SSL=true, EMAIL_PORT=465\n"
                    "  • Use a Gmail App Password (not your normal password)\n"
                    "  • DEFAULT_FROM_EMAIL should usually match EMAIL_HOST_USER\n"
                )
            )
            raise CommandError("Low-level SMTP failed — see output above.") from e

        self.stdout.write(self.style.NOTICE("\n=== Django send (EmailMultiAlternatives) ==="))
        try:
            connection = get_connection(
                backend=settings.EMAIL_BACKEND,
                fail_silently=False,
            )
            msg = EmailMultiAlternatives(
                subject="[test_email] Django SMTP OK",
                body="If you see this, Django email delivery works.",
                from_email=from_email,
                to=[to],
                connection=connection,
            )
            msg.send()
            self.stdout.write(self.style.SUCCESS(f"Sent test email to {to!r} from {from_email!r}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Django send FAILED: {e!r}"))
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            raise CommandError("Django email send failed.") from e
