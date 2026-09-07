from django.core.management.base import BaseCommand
from django.db import transaction

from apps.ref.dedupe import dedupe_tribes
from apps.ref.models import Tribe


class Command(BaseCommand):
    help = "Fold duplicate tribe rows (same parent, same name) into one"

    @transaction.atomic
    def handle(self, *args, **options):
        before = Tribe.objects.count()
        removed = dedupe_tribes()
        self.stdout.write(
            self.style.SUCCESS(
                f"merged {removed} duplicate tribes: {before} -> "
                f"{Tribe.objects.count()}",
            ),
        )
