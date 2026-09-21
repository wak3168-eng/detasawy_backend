import io
import wave

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.corpus.models import Contribution, Prompt
from apps.identity.models import Profile, User


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
})
class ContributionAudioTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="audio-test@example.invalid")
        Profile.objects.create(user=self.user, completed_at=timezone.now())
        self.prompt = Prompt.objects.create(kind="picture", caption_en="Test")
        self.client.force_authenticate(user=self.user)

    def submit(self, text="word", audio=None):
        data = {"prompt": self.prompt.pk, "text": text}
        if audio is not None:
            data["audio"] = audio
        return self.client.post("/api/contributions", data, format="multipart")

    def recording(self, sample=0):
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(sample.to_bytes(2, "little", signed=True) * 160)
        return SimpleUploadedFile("voice.wav", output.getvalue(), "audio/wav")

    def assert_voice_count(self, expected):
        words = self.client.get(f"/api/prompts/{self.prompt.pk}/words")
        self.assertEqual(words.status_code, 200)
        self.assertEqual(words.data[0]["voices"], expected)
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])
        dataset = self.client.get("/api/admin/dataset")
        self.assertEqual(dataset.status_code, 200)
        self.assertEqual(dataset.data["items"][0]["voices"], expected)

    def test_text_only_answer_is_not_counted_as_recorded(self):
        self.assertEqual(self.submit().status_code, 201)
        self.assertFalse(Contribution.objects.get().audio)
        self.assert_voice_count(0)

    def test_non_audio_and_empty_uploads_are_rejected(self):
        for upload in (
            SimpleUploadedFile("notes.txt", b"not a recording", "text/plain"),
            SimpleUploadedFile("empty.wav", b"", "audio/wav"),
        ):
            with self.subTest(name=upload.name):
                self.assertEqual(self.submit(audio=upload).status_code, 400)
                self.assertFalse(Contribution.objects.exists())

    def test_invalid_text_does_not_overwrite_existing_answer(self):
        self.assertEqual(self.submit().status_code, 201)
        for text in ("x" * 201, ["invalid"], 123, None):
            with self.subTest(text=text):
                response = self.client.post("/api/contributions", {
                    "prompt": self.prompt.pk, "text": text,
                }, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(Contribution.objects.get().text_raw, "word")

    def test_legacy_malformed_metadata_does_not_crash_dataset(self):
        self.assertEqual(self.submit().status_code, 201)
        for district, path in (("bad", 123), ({"name": []}, ["bad", {"name": []}])):
            with self.subTest(district=district, path=path):
                Contribution.objects.update(district=district, tribe_path=path)
                self.assert_voice_count(0)

    def test_resubmitting_without_audio_clears_previous_recording(self):
        for replacement in ("word", "different word"):
            with self.subTest(replacement=replacement):
                self.assertEqual(self.submit(audio=self.recording()).status_code, 201)
                self.assert_voice_count(1)
                self.assertEqual(self.submit(text=replacement).status_code, 201)
                row = Contribution.objects.get()
                self.assertEqual(row.text_raw, replacement)
                self.assertFalse(row.audio)
                self.assert_voice_count(0)

    def test_resubmitting_with_audio_replaces_previous_recording(self):
        self.assertEqual(self.submit(audio=self.recording()).status_code, 201)
        replacement = self.recording(sample=100)
        expected = replacement.read()
        replacement.seek(0)
        self.assertEqual(self.submit("new word", replacement).status_code, 201)
        row = Contribution.objects.get()
        self.assertEqual(row.text_raw, "new word")
        with row.audio.open("rb") as audio:
            self.assertEqual(audio.read(), expected)
        self.assert_voice_count(1)

    def test_scene_still_requires_audio_and_preserves_answer_on_rejection(self):
        self.prompt.kind = "scene"
        self.prompt.save(update_fields=["kind"])
        self.assertEqual(self.submit(audio=self.recording()).status_code, 201)
        self.assertEqual(self.submit("replacement").status_code, 400)
        row = Contribution.objects.get()
        self.assertEqual(row.text_raw, "word")
        self.assertTrue(row.audio)
