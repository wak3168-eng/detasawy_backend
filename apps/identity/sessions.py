from datetime import timedelta

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone


@receiver(user_logged_in)
def set_session_deadline(sender, request, user, **kwargs):
    # Covers both API and Django admin sign-in. An absolute deadline prevents
    # background requests or session edits from extending the login indefinitely.
    lifetime = settings.ADMIN_SESSION_AGE if user.is_staff or user.is_superuser else settings.SESSION_COOKIE_AGE
    request.session.set_expiry(timezone.now() + timedelta(seconds=lifetime))
