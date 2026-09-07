import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create the superuser from DJANGO_SUPERUSER_EMAIL (or _USERNAME) and "
        "DJANGO_SUPERUSER_PASSWORD env vars if it doesn't exist. No-op when missing."
    )

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL") or os.environ.get(
            "DJANGO_SUPERUSER_USERNAME",
        )
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not email or not password:
            self.stdout.write("superuser env vars not set — skipping")
            return
        if "@" not in email:
            email = f"{email}@detasawy.com"
        User = get_user_model()
        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(f"superuser '{email}' already exists — skipping")
            return
        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"created superuser '{email}'"))
