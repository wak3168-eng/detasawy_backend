import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create the superuser from DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD "
        "env vars if it doesn't exist. No-op when the vars are missing."
    )

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        if not username or not password:
            self.stdout.write("superuser env vars not set — skipping")
            return
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"superuser '{username}' already exists — skipping")
            return
        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"created superuser '{username}'"))
