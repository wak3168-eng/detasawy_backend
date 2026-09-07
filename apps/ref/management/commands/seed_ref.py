import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.ref.models import (
    Country,
    District,
    Language,
    Province,
    Tehsil,
    Tribe,
    TribeDistrict,
)
from apps.ref.normalize import slug_part

DATA_DIR = Path(__file__).resolve().parents[4] / "data"

CURATED_LANGUAGES = [
    "Pashto (Northern)",
    "Pashto (Southern)",
    "Pashto (Central)",
    "Pashto (Wanetsi)",
    "Hindko",
    "Saraiki",
    "Urdu",
    "Dari",
    "Balochi",
    "Brahui",
    "Khowar",
    "Kohistani",
    "Shina",
    "Gojri",
    "Wakhi",
    "Kalasha",
    "Pashayi",
    "Nuristani",
    "Uzbek",
    "Turkmen",
]


class Command(BaseCommand):
    help = "Seed the reference tables from data/geography.json and data/tribes.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Wipe existing reference data and reseed",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        geography = json.loads((DATA_DIR / "geography.json").read_text(encoding="utf-8"))

        names = set(CURATED_LANGUAGES)
        for country in geography["countries"]:
            for province in country["provinces"]:
                for district in province["districts"]:
                    for part in str(district.get("language") or "").split(";"):
                        part = part.strip()
                        if part:
                            names.add(part)
        new_languages = 0
        for name in sorted(names):
            _, created = Language.objects.get_or_create(
                id=f"lang-{slug_part(name)}", defaults={"name": name},
            )
            new_languages += 1 if created else 0
        if new_languages:
            self.stdout.write(f"languages ensured: {new_languages} added")

        if Country.objects.exists() and not options["force"]:
            self.stdout.write("ref data already present — skipping (use --force to reseed)")
            return

        if options["force"]:
            TribeDistrict.objects.all().delete()
            Tribe.objects.all().delete()
            Tehsil.objects.all().delete()
            District.objects.all().delete()
            Province.objects.all().delete()
            Country.objects.all().delete()

        tribes = json.loads((DATA_DIR / "tribes.json").read_text(encoding="utf-8"))

        for country in geography["countries"]:
            country_row = Country.objects.create(id=country["id"], name=country["name"])
            for province in country["provinces"]:
                province_row = Province.objects.create(
                    id=province["id"], name=province["name"], country=country_row
                )
                for district in province["districts"]:
                    district_row = District.objects.create(
                        id=district["id"],
                        name=district["name"],
                        province=province_row,
                        language=district.get("language") or "",
                    )
                    for tehsil in district["tehsils"]:
                        Tehsil.objects.create(
                            id=tehsil["id"], name=tehsil["name"], district=district_row
                        )

        Tribe.objects.bulk_create(
            Tribe(
                id=node["id"],
                name=node["name"],
                parent_id=node["parentId"],
                level=node["level"],
                level_name=node["levelName"],
                pashto=node.get("pashto") or "",
                country=node["country"],
                aliases=node.get("aliases") or [],
            )
            for node in tribes["nodes"]
        )

        link_roles: dict[tuple[str, str], str] = {}
        for tribe_id, buckets in tribes["tribeDistricts"].items():
            for district_id in buckets.get("presentIn", []):
                link_roles.setdefault((tribe_id, district_id), "present")
            for district_id in buckets.get("dominantIn", []):
                link_roles[(tribe_id, district_id)] = "dominant"
        TribeDistrict.objects.bulk_create(
            TribeDistrict(tribe_id=tribe_id, district_id=district_id, role=role)
            for (tribe_id, district_id), role in link_roles.items()
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"seeded: {Country.objects.count()} countries, "
                f"{Province.objects.count()} provinces, "
                f"{District.objects.count()} districts, "
                f"{Tehsil.objects.count()} tehsils, "
                f"{Tribe.objects.count()} tribes, "
                f"{TribeDistrict.objects.count()} links",
            ),
        )
