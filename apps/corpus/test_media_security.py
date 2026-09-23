from django.core.files.base import ContentFile
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.identity.models import Profile, User
from .models import Contribution, MediaBlob, Prompt


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class MediaSecurityTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="owner@example.invalid")
        self.other = User.objects.create_user(email="other@example.invalid")
        self.admin = User.objects.create_superuser(email="admin@example.invalid")
        self.reviewer = User.objects.create_user(email="reviewer@example.invalid", is_staff=True)
        self.prompt = Prompt.objects.create(kind="picture", caption_en="Sample")
        self.answer = Contribution.objects.create(prompt=self.prompt, contributor=self.owner, text_raw="word", audio=ContentFile(b"0123456789", name="voice.wav"))
        self.photo = MediaBlob.objects.create(sha256="a" * 64, mime="image/jpeg", data=b"photo", size=5)
        Profile.objects.create(user=self.owner, photo_blob=self.photo)
        self.audio_url = f"/api/private/contributions/{self.answer.pk}/audio"
        self.photo_url = f"/api/private/profiles/{self.owner.pk}/photo"

    def test_only_owner_and_superadmin_can_access_private_media(self):
        for user, expected in [(None, 401), (self.other, 404), (self.reviewer, 404), (self.owner, 200), (self.admin, 200)]:
            self.client.force_authenticate(user)
            for url in (self.audio_url, self.photo_url):
                with self.subTest(user=user, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, expected)
                    self.assertEqual(response["Cache-Control"], "private, no-store")
                    response.close()

    def test_legacy_urls_and_conditional_requests_cannot_bypass_permissions(self):
        for user in (None, self.other):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(f"/api/blob/{self.photo.sha256}").status_code, 404)
            self.assertEqual(self.client.get(f"/api/blob/{self.photo.sha256}", HTTP_IF_NONE_MATCH=f'"{self.photo.sha256}"').status_code, 404)
            self.assertEqual(self.client.get(self.answer.audio.url).status_code, 404)
            self.assertEqual(self.client.get(self.audio_url, HTTP_RANGE="bytes=0-3").status_code, 401 if user is None else 404)

    def test_audio_seeking_keeps_permission_and_cache_controls(self):
        self.client.force_authenticate(self.owner)
        for requested, content, content_range in [("bytes=2-5", b"2345", "bytes 2-5/10"), ("bytes=-3", b"789", "bytes 7-9/10"), ("bytes=8-", b"89", "bytes 8-9/10")]:
            response = self.client.get(self.audio_url, HTTP_RANGE=requested)
            self.assertEqual(response.status_code, 206)
            self.assertEqual(b"".join(response.streaming_content), content)
            self.assertEqual(response["Content-Range"], content_range)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            response.close()
        for requested in ("bytes=20-30", "bytes=0-2,4-6", "bytes=-0", "bytes=-", "bytes=8-2"):
            response = self.client.get(self.audio_url, HTTP_RANGE=requested)
            self.assertEqual(response.status_code, 416)

    def test_prompt_blobs_remain_public_but_orphans_and_photos_do_not(self):
        public_blob = MediaBlob.objects.create(sha256="b" * 64, mime="image/jpeg", data=b"prompt", size=6)
        self.assertEqual(self.client.get(f"/api/blob/{public_blob.sha256}").status_code, 404)
        self.prompt.blob = public_blob
        self.prompt.save()
        self.assertEqual(self.client.get(f"/api/blob/{public_blob.sha256}").status_code, 200)
        self.prompt.blob = self.photo
        self.prompt.save()
        self.assertEqual(self.client.get(f"/api/blob/{self.photo.sha256}").status_code, 404)

    def test_public_files_must_belong_to_a_prompt_not_a_contribution(self):
        self.prompt.media.save("prompt.wav", ContentFile(b"public"))
        response = self.client.get(f"/api/media/prompts/{self.prompt.pk}")
        self.assertEqual(response.status_code, 200)
        response.close()
        response = self.client.get(self.prompt.media.url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.prompt.media = self.answer.audio.name
        self.prompt.save()
        self.assertEqual(self.client.get(f"/api/media/prompts/{self.prompt.pk}").status_code, 404)
        self.assertEqual(self.client.get(self.answer.audio.url).status_code, 404)

    def test_serializers_never_return_a_direct_private_storage_url(self):
        self.client.force_authenticate(self.admin)
        result = self.client.get("/api/admin/contributions").data
        self.assertEqual(result["items"][0]["audioUrl"], self.audio_url)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get("/api/auth/me").data["profile"]["photoUrl"], self.photo_url)
