import io
from datetime import timedelta
from PIL import Image
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase
from apps.corpus.models import Prompt, Contribution
from apps.identity.models import User
from apps.ref.models import Country, Province
from apps.portal.models import Campaign


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AdminWorkspaceTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="owner@example.invalid")
        self.contributor = User.objects.create_user(email="person@example.invalid")
        self.reviewer = User.objects.create_user(email="review@example.invalid", is_staff=True)
        self.reviewer.groups.add(Group.objects.get_or_create(name="Reviewers")[0])
        self.manager = User.objects.create_user(email="campaign@example.invalid", is_staff=True)
        self.manager.groups.add(Group.objects.get_or_create(name="Campaign managers")[0])
        self.client.force_authenticate(self.admin)

    def test_role_permissions_for_every_workspace(self):
        for user, permitted in [
            (None, set()), (self.contributor, set()),
            (self.reviewer, {"overview", "suggestions"}),
            (self.manager, {"overview", "prompts", "campaigns"}),
            (self.admin, {"overview", "suggestions", "prompts", "campaigns", "users", "dataset", "contributions"}),
        ]:
            self.client.force_authenticate(user)
            for endpoint in ["overview", "suggestions", "prompts", "campaigns", "users", "dataset", "contributions"]:
                with self.subTest(user=user, endpoint=endpoint):
                    response = self.client.get("/api/admin/" + endpoint)
                    if endpoint in permitted:
                        self.assertEqual(response.status_code, 200)
                    else:
                        self.assertIn(response.status_code, (401, 403))

    def test_prompt_pagination_reaches_records_beyond_old_limit(self):
        Prompt.objects.bulk_create([Prompt(kind="picture", caption_en=f"Item {i}") for i in range(65)])
        ids = []
        for page in range(1, 5):
            response = self.client.get("/api/admin/prompts", {"page": page})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["total"], 65)
            ids.extend(row["id"] for row in response.data["items"])
        self.assertEqual(len(set(ids)), 65)
        self.assertEqual(len(ids), 65)
        self.assertEqual(len(self.client.get("/api/admin/prompts").data), 50)

    def test_prompt_filters_and_invalid_queries(self):
        Prompt.objects.create(kind="scene", caption_en="Market", active=False)
        Prompt.objects.create(kind="picture", caption_en="Market")
        result = self.client.get("/api/admin/prompts?page=1&kind=scene&active=false&q=Market")
        self.assertEqual(result.data["total"], 1)
        for query in ("page=0", "page=no", "pageSize=51", "kind=invalid", "active=maybe"):
            self.assertEqual(self.client.get("/api/admin/prompts?" + query).status_code, 400)

    def test_scene_upload_is_an_image_and_preserves_metadata(self):
        image = io.BytesIO()
        Image.new("RGB", (8, 8), "blue").save(image, "PNG")
        response = self.client.post("/api/admin/prompts", {
            "kind": "scene", "captionEn": "Scene", "sourceUrl": "https://example.com/source",
            "licence": "CC0", "media": SimpleUploadedFile("scene.png", image.getvalue(), "image/png"),
        }, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["sourceUrl"], "https://example.com/source")
        self.assertTrue(Prompt.objects.get().blob_id)
        self.assertEqual(self.client.post("/api/admin/prompts", {
            "kind": "scene", "media": SimpleUploadedFile("wrong.wav", b"bad", "audio/wav"),
        }, format="multipart").status_code, 400)

    def test_invalid_prompt_payloads_do_not_write(self):
        for data in [
            {"kind": "picture", "mediaUrl": "javascript:alert(1)"},
            {"kind": "picture", "mediaUrl": "ftp://example.com/file.png"},
            {"kind": "scene", "mediaUrl": []},
            {"kind": "voice"},
            {"kind": "picture", "mediaUrl": "https://example.com/a.png", "captionEn": "x" * 161},
        ]:
            self.assertEqual(self.client.post("/api/admin/prompts", data, format="json").status_code, 400)
        self.assertEqual(Prompt.objects.count(), 0)

    def test_audio_filters_and_overview_do_not_invent_recordings_or_words(self):
        picture = Prompt.objects.create(kind="picture", caption_en="Door")
        scene = Prompt.objects.create(kind="scene", caption_en="Street")
        Contribution.objects.create(prompt=picture, contributor=self.contributor, text_raw="door", text_norm="door", district={"id": "sample", "name": "Sample"})
        Contribution.objects.create(prompt=scene, contributor=self.contributor, text_raw="", text_norm="", audio="example.wav", district="malformed legacy")
        recorded = self.client.get("/api/admin/contributions?audio=yes&page=1")
        self.assertEqual(recorded.data["total"], 1)
        self.assertTrue(recorded.data["items"][0]["audioUrl"].startswith("/api/private/contributions/"))
        self.assertIsNone(recorded.data["items"][0]["district"])
        self.assertEqual(recorded["Cache-Control"], "private, no-store")
        missing = self.client.get("/api/admin/contributions?audio=no&page=1")
        self.assertEqual(missing.data["total"], 1)
        self.assertIsNone(missing.data["items"][0]["audioUrl"])
        self.assertEqual(self.client.get(f"/api/admin/contributions?prompt={scene.id}").data["total"], 1)
        overview = self.client.get("/api/admin/overview").data
        self.assertEqual(overview["picturesAnswered"], 1)
        self.assertEqual(overview["uniqueWords"], 1)
        self.assertEqual(overview["voiceNotes"], 1)
        self.assertEqual(overview["districtsCovered"], 1)

    def test_dataset_rejects_invalid_pagination(self):
        for query in (
            "offset=-1", "limit=0", "limit=51", "all=maybe", "offset=abc",
            "groupBy=unknown", "minSample=0", "minSample=101",
        ):
            self.assertEqual(self.client.get("/api/admin/dataset?" + query).status_code, 400)

    def test_dataset_clubs_pictures_and_answers_into_selectable_group_views(self):
        cricket = Prompt.objects.create(kind="picture", caption_en="Cricket")
        unused = Prompt.objects.create(kind="picture", caption_en="Unused")
        contributors = [self.contributor] + [
            User.objects.create_user(email=f"speaker-{index}@example.invalid")
            for index in range(3)
        ]
        places = [
            ({"id": "pk", "name": "Pakistan"}, {"id": "swat", "name": "Swat"}, "کرکټ"),
            ({"id": "pk", "name": "Pakistan"}, {"id": "swat", "name": "Swat"}, "کرکټ"),
            ({"id": "pk", "name": "Pakistan"}, {"id": "peshawar", "name": "Peshawar"}, "کرکټ"),
            ({"id": "af", "name": "Afghanistan"}, {"id": "kabul", "name": "Kabul"}, "بل نوم"),
        ]
        for user, (country, district, word) in zip(contributors, places):
            Contribution.objects.create(
                prompt=cricket, contributor=user, text_raw=word, text_norm=word,
                country=country, district=district,
                tribe_path=[
                    {"id": "tribe-a", "name": "Tribe A"},
                    {"id": "clan-a", "name": "Clan A"},
                    {"id": "branch-a", "name": "Branch A"},
                ],
            )

        result = self.client.get(
            "/api/admin/dataset?all=1&groupBy=country&group=pk&minSample=3",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["total"], 2)
        self.assertEqual(result.data["summary"]["responses"], 3)
        self.assertEqual(result.data["summary"]["answeredPictures"], 1)
        self.assertEqual(
            {group["label"]: group["responses"] for group in result.data["grouping"]["groups"]},
            {"Pakistan": 3, "Afghanistan": 1},
        )
        cricket_row = next(item for item in result.data["items"] if item["id"] == cricket.id)
        self.assertEqual(cricket_row["representative"]["word"], "کرکټ")
        self.assertEqual(cricket_row["representative"]["status"], "representative")
        self.assertEqual(cricket_row["representative"]["share"], 1.0)
        unused_row = next(item for item in result.data["items"] if item["id"] == unused.id)
        self.assertIsNone(unused_row["representative"])

        branch = self.client.get(
            "/api/admin/dataset?groupBy=subclan&group=branch-a&minSample=3",
        )
        self.assertEqual(branch.data["summary"]["responses"], 4)
        self.assertEqual(branch.data["items"][0]["answers"], 4)

    def test_users_are_paginated_and_superadmin_cannot_be_demoted(self):
        result = self.client.get("/api/admin/users?page=1&pageSize=2")
        self.assertEqual(result.data["total"], 4)
        self.assertEqual(len(result.data["items"]), 2)
        response = self.client.post("/api/admin/users/role", {"email": self.admin.email, "role": "contributor"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser)
        for endpoint, payload in [("role", {"email": [], "role": "reviewer"}), ("create", {"name": {}, "email": []})]:
            self.assertEqual(self.client.post("/api/admin/users/" + endpoint, payload, format="json").status_code, 400)

    def test_campaign_scope_dates_and_ending_upcoming(self):
        now = timezone.now()
        country = Country.objects.create(id="qa-country", name="Sample")
        province = Province.objects.create(id="qa-province", name="Canonical province", country=country)
        data = {"name": "Drive", "scopeType": "province", "scopeId": "missing",
                "startsAt": (now + timedelta(days=1)).isoformat(), "endsAt": (now + timedelta(days=3)).isoformat()}
        self.assertEqual(self.client.post("/api/admin/campaigns", data, format="json").status_code, 400)
        data.update(scopeId=province.id, scopeName="Spoofed")
        result = self.client.post("/api/admin/campaigns", data, format="json")
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["scopeName"], province.name)
        ended = self.client.post(f'/api/admin/campaigns/{result.data["id"]}/end')
        self.assertEqual(ended.data["status"], "ended")
        data["startsAt"] = "2026-99-99"
        self.assertEqual(self.client.post("/api/admin/campaigns", data, format="json").status_code, 400)
        self.assertEqual(Campaign.objects.count(), 1)

