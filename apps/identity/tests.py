from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.identity.models import Profile, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuthThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        User.objects.create_user(email="login@example.invalid", password="test-password")

    def test_login_throttles_after_ten_attempts(self):
        for _ in range(10):
            response = self.client.post("/api/auth/login", {
                "email": "login@example.invalid", "password": "wrong",
            }, format="json")
            self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/auth/login", {
            "email": "login@example.invalid", "password": "wrong",
        }, format="json")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    def test_valid_login_still_works(self):
        response = self.client.post("/api/auth/login", {
            "email": "login@example.invalid", "password": "test-password",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)


class ProfileValidationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="profile@example.invalid")
        self.profile = Profile.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_invalid_places_are_rejected_before_saving(self):
        for field in ("country", "residence", "province", "district", "tehsil"):
            for value in ("bad", [], {"name": []}, {"name": "District", "id": []}):
                with self.subTest(field=field, value=value):
                    response = self.client.put("/api/profile", {field: value}, format="json")
                    self.assertEqual(response.status_code, 400)
                    self.profile.refresh_from_db()
                    self.assertIsNone(getattr(self.profile, field))

    def test_invalid_tribe_paths_are_rejected(self):
        for value in ("bad", 123, {}, [None], ["bad"], [{"name": []}]):
            with self.subTest(value=value):
                response = self.client.put("/api/profile", {"tribePath": value}, format="json")
                self.assertEqual(response.status_code, 400)

    def test_valid_place_and_empty_optional_fields_are_preserved(self):
        payload = {"district": {"name": "Example", "id": "example"},
                   "country": None, "tribePath": []}
        response = self.client.put("/api/profile", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.district, payload["district"])
        self.assertEqual(self.profile.tribe_path, [])
