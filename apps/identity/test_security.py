from datetime import timedelta
from importlib import import_module
from unittest.mock import patch

from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from .models import Profile, RateLimitBucket, User
from .throttles import ApiThrottle, AuthThrottle, client_ip, consume


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CookieSecurityTests(APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(email="session@example.invalid", password="test-password")

    def csrf(self, client=None):
        response = (client or self.client).get("/api/auth/csrf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        return response.data["csrfToken"]

    def login(self, client=None):
        client = client or self.client
        token = self.csrf(client)
        response = client.post("/api/auth/login", {
            "email": self.user.email, "password": "test-password",
        }, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200, response.data)
        return response

    def test_login_requires_csrf_even_without_a_session(self):
        response = self.client.post("/api/auth/login", {
            "email": self.user.email, "password": "test-password",
        }, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Session.objects.exists())

    def test_login_rotates_session_and_sets_expiry_without_returning_credentials(self):
        engine = import_module(settings.SESSION_ENGINE)
        old = engine.SessionStore()
        old["untrusted"] = True
        old.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = old.session_key
        response = self.login()
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertNotEqual(cookie.value, old.session_key)
        self.assertFalse(Session.objects.filter(session_key=old.session_key).exists())
        self.assertNotIn("token", response.data)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        row = Session.objects.get(session_key=cookie.value)
        self.assertLessEqual((row.expire_date - timezone.now()).total_seconds(), settings.SESSION_COOKIE_AGE)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True, SESSION_COOKIE_NAME="__Host-detasawy_session")
    def test_production_cookie_flags(self):
        response = self.login()
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["path"], "/")
        self.assertFalse(cookie["domain"])

    def test_admin_has_shorter_fixed_session(self):
        self.user.is_superuser = True
        self.user.save()
        response = self.login()
        session = Session.objects.get(session_key=response.cookies[settings.SESSION_COOKIE_NAME].value)
        expires = session.expire_date
        self.assertLessEqual((expires - timezone.now()).total_seconds(), settings.ADMIN_SESSION_AGE)
        self.client.get("/api/auth/me")
        session.refresh_from_db()
        self.assertEqual(session.expire_date, expires)

    def test_django_admin_login_also_uses_fixed_short_deadline(self):
        self.user.is_staff = True
        self.user.save()
        self.assertTrue(self.client.login(email=self.user.email, password="test-password"))
        deadline = self.client.session.get_expiry_date()
        self.assertLessEqual((deadline - timezone.now()).total_seconds(), settings.ADMIN_SESSION_AGE)
        self.assertIsInstance(self.client.session["_session_expiry"], str)

    def test_expired_session_and_legacy_token_are_rejected(self):
        response = self.login()
        Session.objects.filter(session_key=response.cookies[settings.SESSION_COOKIE_NAME].value).update(expire_date=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        legacy = Token.objects.create(user=self.user)
        other = APIClient()
        other.credentials(HTTP_AUTHORIZATION=f"Token {legacy.key}")
        self.assertEqual(other.get("/api/auth/me").status_code, 401)

    def test_mutation_requires_csrf_and_rejects_an_untrusted_origin(self):
        response = self.login()
        token = response.data["csrfToken"]
        self.assertEqual(self.client.put("/api/profile", {"city": "new"}, format="json").status_code, 403)
        self.assertEqual(self.client.put("/api/profile", {"city": "new"}, format="json", HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://attacker.vercel.app").status_code, 403)
        self.assertEqual(self.client.put("/api/profile", {"city": "new"}, format="json", HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN="https://detasawy.com").status_code, 200)

    def test_logout_revokes_server_session_and_cannot_be_forged(self):
        response = self.login()
        saved_cookie = response.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 403)
        self.assertEqual(self.client.post("/api/auth/logout", HTTP_X_CSRFTOKEN=response.data["csrfToken"]).status_code, 204)
        self.client.cookies[settings.SESSION_COOKIE_NAME] = saved_cookie
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_password_change_invalidates_all_sessions(self):
        self.login()
        second = APIClient(enforce_csrf_checks=True)
        self.login(second)
        self.user.set_password("replacement-password")
        self.user.save()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(second.get("/api/auth/me").status_code, 401)

    def test_arbitrary_vercel_origins_do_not_get_cors_access(self):
        self.assertNotIn("Access-Control-Allow-Origin", self.client.get("/api/auth/csrf", HTTP_ORIGIN="https://random.vercel.app"))


class SharedRateLimitTests(APITestCase):
    def test_limits_are_shared_between_clients_and_expire(self):
        for _ in range(10):
            response = APIClient().post("/api/auth/login", {"email": "no@example.invalid", "password": "bad"}, format="json")
            self.assertEqual(response.status_code, 400)
        response = APIClient().post("/api/auth/login", {"email": "no@example.invalid", "password": "bad"}, format="json")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        RateLimitBucket.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(APIClient().post("/api/auth/login", {"email": "no@example.invalid", "password": "bad"}, format="json").status_code, 400)

    def test_account_limit_survives_ip_rotation_and_case_changes(self):
        for index in range(11):
            response = self.client.post("/api/auth/login", {"email": "No@EXAMPLE.invalid" if index % 2 else "no@example.invalid", "password": "bad"}, format="json", REMOTE_ADDR=f"192.0.2.{index+1}")
        self.assertEqual(response.status_code, 429)
        self.assertTrue(all(len(key) == 64 for key in RateLimitBucket.objects.values_list("key", flat=True)))

    def test_django_admin_cannot_bypass_login_throttle(self):
        for _ in range(10):
            self.client.post("/api/auth/login", {"email": "no@example.invalid", "password": "bad"}, format="json")
        response = self.client.post("/admin/login/", {"username": "no@example.invalid", "password": "bad"})
        self.assertEqual(response.status_code, 429)

    def test_untrusted_forwarding_headers_are_ignored(self):
        from django.test import RequestFactory
        request = RequestFactory().get("/", REMOTE_ADDR="192.0.2.1", HTTP_X_FORWARDED_FOR="198.51.100.1")
        with override_settings(TRUSTED_PROXY_HOPS=0):
            self.assertEqual(client_ip(request), "192.0.2.1")
        with override_settings(TRUSTED_PROXY_HOPS=1):
            self.assertEqual(client_ip(request), "198.51.100.1")

    def test_uploads_and_writes_have_separate_shared_limits(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from rest_framework.request import Request
        user = User.objects.create_user(email="upload@example.invalid")
        raw = APIRequestFactory().post("/api/contributions", {"text": "word"}, format="multipart")
        force_authenticate(raw, user)
        request = Request(raw)
        for _ in range(20):
            self.assertTrue(ApiThrottle().allow_request(request, None))
        throttle = ApiThrottle()
        self.assertFalse(throttle.allow_request(request, None))
        self.assertGreater(throttle.wait(), 0)
        self.assertEqual(consume("independent", "another-user", 1, 60), 0)

    def test_hourly_login_limit_survives_short_window_expiry(self):
        now = timezone.now()
        for minute in range(3):
            with patch("apps.identity.throttles.timezone.now", return_value=now + timedelta(minutes=minute)):
                for index in range(10):
                    response = self.client.post("/api/auth/login", {"email": "hour@example.invalid", "password": "bad"}, format="json", REMOTE_ADDR=f"192.0.2.{minute*10+index+1}")
                    self.assertEqual(response.status_code, 400)
        with patch("apps.identity.throttles.timezone.now", return_value=now + timedelta(minutes=3)):
            response = self.client.post("/api/auth/login", {"email": "hour@example.invalid", "password": "bad"}, format="json", REMOTE_ADDR="192.0.2.99")
            self.assertEqual(response.status_code, 429)
