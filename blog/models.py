from django.db import models


class BlogEntry(models.Model):
    """Persisted Oracle→Mistral draft and optional WordPress XML-RPC publish result."""

    title = models.CharField(max_length=500, blank=True)
    oracle_script = models.TextField()
    generated_body = models.TextField(blank=True)
    mistral_model = models.CharField(max_length=100, default="mistral-large-latest")
    wordpress_category_name = models.CharField(max_length=200, blank=True)
    wordpress_post_id = models.PositiveIntegerField(null=True, blank=True)
    wordpress_post_type = models.CharField(max_length=20, default="post")
    wordpress_status = models.CharField(max_length=20, default="draft")
    publish_error = models.TextField(blank=True)
    # One-click email link: secret segment in /publish/<pk>/<token>/ until used or cleared after live publish
    publish_secret_token = models.CharField(max_length=64, blank=True)
    email_notify_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title or f"BlogEntry #{self.pk}"
