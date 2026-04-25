from django.contrib import admin

from blog.models import BlogEntry


@admin.register(BlogEntry)
class BlogEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "wordpress_status",
        "wordpress_post_id",
        "wordpress_category_name",
        "created_at",
    )
    readonly_fields = ("created_at", "updated_at")
    search_fields = ("title", "oracle_script")
