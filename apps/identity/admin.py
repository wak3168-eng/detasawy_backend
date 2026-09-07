from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.identity.models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "name", "is_active", "is_staff", "date_joined"]
    search_fields = ["email", "name"]
    inlines = [ProfileInline]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Personal", {"fields": ["name", "consent_version", "consented_at"]}),
        (
            "Permissions",
            {"fields": ["is_active", "is_staff", "is_superuser", "groups"]},
        ),
        ("Dates", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {"fields": ["email", "password1", "password2"]}),
    ]


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "completed_at", "updated_at"]
    search_fields = ["user__email", "user__name"]
