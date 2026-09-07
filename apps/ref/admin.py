from django.contrib import admin

from apps.ref.models import Country, District, Province, Tehsil, Tribe, TribeDistrict

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
