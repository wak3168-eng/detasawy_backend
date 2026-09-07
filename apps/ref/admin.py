import difflib

from django.contrib import admin

from apps.ref.models import (
    Country,
    District,
    Language,
    Province,
    Suggestion,
    Tehsil,
    Tribe,
    TribeDistrict,
)
from apps.ref.normalize import normalize_name
from apps.ref.services import (
    approve_suggestion,
    merge_suggestion,
    reject_suggestion,
)

admin.site.site_header = "Detasawy administration"
admin.site.site_title = "Detasawy admin"


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "country"]
    list_filter = ["country"]
    search_fields = ["name"]


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "province", "language"]
    list_filter = ["province"]
    search_fields = ["name"]


@admin.register(Tehsil)
class TehsilAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "district"]
    list_filter = ["district__province"]
    search_fields = ["name"]


@admin.register(Tribe)
class TribeAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "parent", "level", "level_name", "country"]
    list_filter = ["country", "level_name"]
    search_fields = ["name", "pashto", "aliases"]
    raw_id_fields = ["parent"]


@admin.register(TribeDistrict)
class TribeDistrictAdmin(admin.ModelAdmin):
    list_display = ["tribe", "district", "role"]
    list_filter = ["role", "district"]
    search_fields = ["tribe__name", "district__name"]


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "kind",
        "parent_name",
        "times_suggested",
        "suggested_by",
        "status",
        "created_at",
    ]
    list_filter = ["status", "kind"]
    search_fields = ["name", "parent_name", "suggested_by__email"]
    raw_id_fields = ["merge_into"]
    readonly_fields = [
        "kind",
        "name",
        "normalized_name",
        "parent_id",
        "parent_name",
        "suggested_by",
        "times_suggested",
        "status",
        "resolved_ref_id",
        "reviewed_by",
        "reviewed_at",
        "created_at",
        "possible_duplicates",
    ]
    fields = [
        "kind",
        "name",
        "parent_name",
        "possible_duplicates",
        "merge_into",
        "note",
        "status",
        "resolved_ref_id",
        "suggested_by",
        "times_suggested",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    ]
    actions = ["approve_selected", "merge_selected", "reject_selected"]

    @admin.display(description="Possible duplicates")
    def possible_duplicates(self, obj):
        if obj is None or obj.kind != "tribe":
            return "—"
        if obj.parent_id:
            siblings = Tribe.objects.filter(parent_id=obj.parent_id)
        else:
            siblings = Tribe.objects.filter(parent__isnull=True)
        by_norm = {normalize_name(t.name): t for t in siblings}
        close = difflib.get_close_matches(
            obj.normalized_name, by_norm.keys(), n=3, cutoff=0.6,
        )
        if not close:
            return "none found"
        return "; ".join(f"{by_norm[n].name} ({by_norm[n].id})" for n in close)

    def _run(self, request, queryset, action, label):
        done, failed = 0, []
        for suggestion in queryset.filter(status="pending"):
            try:
                action(suggestion, request.user)
                done += 1
            except ValueError as error:
                failed.append(f"{suggestion.name}: {error}")
        if done:
            self.message_user(request, f"{label} {done} suggestion(s).")
        for message in failed:
            self.message_user(request, message, level="ERROR")

    @admin.action(description="Approve — create the entry and update profiles")
    def approve_selected(self, request, queryset):
        self._run(request, queryset, approve_suggestion, "Approved")

    @admin.action(description="Merge into the chosen tribe (set 'merge into' first)")
    def merge_selected(self, request, queryset):
        self._run(request, queryset, merge_suggestion, "Merged")

    @admin.action(description="Reject")
    def reject_selected(self, request, queryset):
        self._run(request, queryset, reject_suggestion, "Rejected")
