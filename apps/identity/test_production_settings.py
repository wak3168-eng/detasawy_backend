import os
import runpy
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase


class ProductionSettingsTests(SimpleTestCase):
    def load(self, **overrides):
        env = {
            "DEBUG": "false",
            "SECRET_KEY": "test-only-configuration-key-with-over-fifty-characters-123456789",
            "DATABASE_URL": "sqlite:///:memory:",
            **overrides,
        }
        with patch.dict(os.environ, env, clear=True):
            return runpy.run_path(str(settings.BASE_DIR / "config" / "settings.py"))

    def test_production_cookie_and_transport_defaults(self):
        config = self.load()
        for name in ("SESSION_COOKIE_SECURE", "SESSION_COOKIE_HTTPONLY", "CSRF_COOKIE_SECURE", "CSRF_COOKIE_HTTPONLY", "SECURE_SSL_REDIRECT"):
            self.assertTrue(config[name], name)
        self.assertTrue(config["SESSION_COOKIE_NAME"].startswith("__Host-"))
        self.assertEqual(config["CORS_ALLOWED_ORIGIN_REGEXES"], [])

    def test_unsafe_configuration_fails_startup(self):
        for override in (
            {"SECRET_KEY": ""}, {"SECRET_KEY": "a" * 60},
            {"SECRET_KEY": "django-insecure-" + "abcde" * 15},
            {"ALLOWED_HOSTS": "*"}, {"ALLOWED_HOSTS": ".vercel.app"},
            {"CSRF_TRUSTED_ORIGINS": "https://*.vercel.app"},
            {"CSRF_TRUSTED_ORIGINS": "http://detasawy.com"},
            {"CORS_ALLOWED_ORIGINS": "*"},
        ):
            with self.subTest(override=override), self.assertRaises(ImproperlyConfigured):
                self.load(**override)
