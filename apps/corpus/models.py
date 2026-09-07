from django.conf import settings
from django.db import models


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
