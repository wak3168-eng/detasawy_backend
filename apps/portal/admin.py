from django.contrib import admin

from apps.portal.models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "scope_type",
        "scope_name",
        "starts_at",
        "ends_at",
        "is_live_now",
        "created_by",
    ]
    list_filter = ["scope_type"]
    search_fields = ["name", "scope_name"]
    readonly_fields = ["created_by", "created_at"]

    @admin.display(boolean=True, description="Live")
    def is_live_now(self, obj):
        return obj.is_live

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
