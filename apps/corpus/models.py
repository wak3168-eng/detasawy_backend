from django.conf import settings
from django.db import models


class Contribution(models.Model):
    """One contributor's answer to a prompt: the Pashto word as written,
    optionally spoken, with dialect labels snapshotted from the profile."""

    prompt = models.ForeignKey(
        "corpus.Prompt", on_delete=models.CASCADE, related_name="contributions"
    )
    contributor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contributions",
    )
    text_raw = models.CharField(max_length=200)
    text_norm = models.CharField(max_length=200)
    audio = models.FileField(
        upload_to="contributions/%Y/%m/", blank=True, null=True
    )
    district = models.JSONField(null=True, blank=True)
    tribe_path = models.JSONField(default=list, blank=True)
    language = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["prompt", "contributor"], name="one_answer_per_prompt"
            ),
        ]

    def __str__(self):
        return f"{self.text_raw} ({self.contributor})"


class MediaBlob(models.Model):
    """Prompt media stored as bytes in Postgres itself, so images survive
    restarts and redeploys without external object storage. Content-addressed
    by sha256 — identical images are stored once."""

    sha256 = models.CharField(max_length=64, unique=True)
    mime = models.CharField(max_length=50)
    data = models.BinaryField()
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sha256[:12]} ({self.mime}, {self.size} bytes)"


class Prompt(models.Model):
    """A picture or voice note uploaded by admins and served randomly to
    contributors as the seed of a contribution."""

    KIND_CHOICES = [("picture", "picture"), ("voice", "voice")]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    blob = models.ForeignKey(
        "corpus.MediaBlob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prompts",
    )
    media = models.FileField(upload_to="prompts/%Y/%m/", blank=True, null=True)
    media_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="External media URL (e.g. Wikimedia Commons) instead of an upload.",
    )
    source_url = models.URLField(max_length=500, blank=True)
    licence = models.CharField(max_length=200, blank=True)
    caption_en = models.CharField(
        max_length=160,
        blank=True,
        help_text="English gloss shown alongside a picture.",
    )
    caption_ps = models.CharField(
        max_length=160,
        blank=True,
        help_text="Optional Pashto text (e.g. what the voice note says).",
    )
    active = models.BooleanField(default=True)
    served_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prompts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def resolve_media_url(self, request):
        if self.blob_id:
            return request.build_absolute_uri(f"/api/blob/{self.blob.sha256}")
        if self.media_url:
            return self.media_url
        if self.media:
            return request.build_absolute_uri(self.media.url)
        return ""

    def __str__(self):
        return f"{self.kind}: {self.caption_en or self.media_url or self.media.name}"
