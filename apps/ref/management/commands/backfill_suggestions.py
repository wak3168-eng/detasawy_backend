from django.core.management.base import BaseCommand

from apps.identity.models import Profile
from apps.ref.services import capture_suggestions


class Command(BaseCommand):
    help = "Scan existing profiles for pending entries and queue them for review"

    def handle(self, *args, **options):
        created = 0
        for profile in Profile.objects.all():
            created += capture_suggestions(profile)
        self.stdout.write(self.style.SUCCESS(f"queued {created} new suggestions"))
