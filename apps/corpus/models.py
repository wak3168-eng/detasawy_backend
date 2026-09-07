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


class Prompt(models.Model):
    """A picture or voice note uploaded by admins and served randomly to
    contributors as the seed of a contribution."""

    KIND_CHOICES = [("picture", "picture"), ("voice", "voice")]

    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    media = models.FileField(upload_to="prompts/%Y/%m/")
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

    def __str__(self):
        return f"{self.kind}: {self.caption_en or self.media.name}"
