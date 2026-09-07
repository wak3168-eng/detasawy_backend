from django.conf import settings
from django.db import models
from django.utils import timezone


class Campaign(models.Model):
    """A time-boxed drive — a district race, a themed push, a seasonal event."""

    SCOPE_CHOICES = [
        ("all", "everyone"),
        ("district", "district"),
        ("province", "province"),
    ]

    name = models.CharField(max_length=120)
    description = models.CharField(max_length=200, blank=True)
    scope_type = models.CharField(max_length=10, choices=SCOPE_CHOICES, default="all")
    scope_id = models.CharField(
        max_length=120, blank=True, help_text="Ref id (e.g. pk-kp-khyber) when scoped.",
    )
    scope_name = models.CharField(max_length=120, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ends_at"]

    def __str__(self):
        return self.name

    @property
    def is_live(self):
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at
