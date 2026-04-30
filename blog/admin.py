from django.contrib import admin

from blog.models import BlogEntry, CustomerProfile


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "email_verified",
        "tier",
        "posts_per_week",
        "publish_timezone",
        "trial_ends_at",
        "paid_current_period",
        "billing_setup_complete",
    )
    list_filter = ("email_verified", "tier", "paid_current_period")
    search_fields = ("user__email", "user__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(BlogEntry)
class BlogEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "owner",
        "approval_status",
        "wordpress_status",
        "wordpress_post_id",
        "scheduled_publish_at",
        "created_at",
    )
    list_filter = ("approval_status", "wordpress_status")
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("title", "oracle_script", "customer_brief", "customer_edited_body")
