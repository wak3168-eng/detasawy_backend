from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.identity.models import RateLimitBucket


class Command(BaseCommand):
    help = "Remove expired sessions and rate-limit counters. Run daily."

    def handle(self, *args, **options):
        now = timezone.now()
        Session.objects.filter(expire_date__lt=now).delete()
        RateLimitBucket.objects.filter(expires_at__lt=now).delete()
        self.stdout.write("Expired security state removed.")
