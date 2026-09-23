import hashlib
import hmac
import ipaddress
import math
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.throttling import BaseThrottle

from .models import RateLimitBucket


def client_ip(request):
    address = request.META.get("REMOTE_ADDR", "unknown")
    hops = settings.TRUSTED_PROXY_HOPS
    if hops:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")
        if len(forwarded) >= hops:
            address = forwarded[-hops].strip()
    try:
        return str(ipaddress.ip_address(address))
    except ValueError:
        return "unknown"


def consume(scope, identity, limit, seconds):
    """Serialize each counter in Postgres so parallel workers cannot lose updates."""
    key = hmac.new(settings.SECRET_KEY.encode(), f"{scope}:{identity}".encode(), hashlib.sha256).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        RateLimitBucket.objects.get_or_create(key=key, defaults={"expires_at": now})
        bucket = RateLimitBucket.objects.select_for_update().get(key=key)
        if bucket.expires_at <= now:
            bucket.count = 0
            bucket.expires_at = now + timedelta(seconds=seconds)
        if bucket.count >= limit:
            return max(1, math.ceil((bucket.expires_at - now).total_seconds()))
        bucket.count += 1
        bucket.save(update_fields=["count", "expires_at"])
    return 0


class SharedThrottle(BaseThrottle):
    retry_after = 0

    def limits(self, request):
        return []

    def allow_request(self, request, view):
        self.retry_after = 0
        for scope, identity, limit, seconds in self.limits(request):
            self.retry_after = max(self.retry_after, consume(scope, identity, limit, seconds))
        return self.retry_after == 0

    def wait(self):
        return self.retry_after


class ApiThrottle(SharedThrottle):
    def limits(self, request):
        authed = request.user.is_authenticated
        identity = f"user:{request.user.pk}" if authed else f"ip:{client_ip(request)}"
        limits = [("api", identity, 300 if authed else 120, 60)]
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            limits.append(("write", identity, 60, 60))
            if request.content_type.startswith("multipart/"):
                limits += [("upload", identity, 20, 60), ("upload-day", identity, 200, 86400)]
        return limits


class AuthThrottle(SharedThrottle):
    def limits(self, request):
        email = request.data.get("email", "")
        email = email.strip().casefold() if isinstance(email, str) else "invalid"
        ip = client_ip(request)
        return [
            ("login-ip", ip, 10, 60),
            ("login-ip-hour", ip, 100, 3600),
            ("login-account", email, 10, 60),
            ("login-account-hour", email, 30, 3600),
        ]
