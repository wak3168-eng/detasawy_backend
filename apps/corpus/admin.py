from django.contrib import admin
from django.utils.html import format_html

from apps.corpus.models import Prompt


@admin.register(Prompt)
class PromptAdmin(admin.ModelAdmin):
    list_display = ["kind", "caption_en", "active", "served_count", "created_by", "created_at", "preview"]
    list_filter = ["kind", "active"]
    search_fields = ["caption_en", "caption_ps"]
    readonly_fields = ["served_count", "created_by", "created_at", "preview"]
    fields = ["kind", "media", "preview", "caption_en", "caption_ps", "active", "served_count", "created_by", "created_at"]

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj is None or not obj.media:
            return "—"
        if obj.kind == "picture":
            return format_html(
                '<img src="{}" style="max-height:120px;border-radius:8px" />',
                obj.media.url,
            )
        return format_html(
            '<audio controls src="{}" style="max-width:260px"></audio>',
            obj.media.url,
        )

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
