from django.conf import settings
from django.db import models


class Country(models.Model):
    id = models.SlugField(primary_key=True, max_length=40)
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "countries"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Province(models.Model):
    id = models.SlugField(primary_key=True, max_length=80)
    name = models.CharField(max_length=120)
    country = models.ForeignKey(
        Country, on_delete=models.CASCADE, related_name="provinces"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class District(models.Model):
    id = models.SlugField(primary_key=True, max_length=120)
    name = models.CharField(max_length=120)
    province = models.ForeignKey(
        Province, on_delete=models.CASCADE, related_name="districts"
    )
    language = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tehsil(models.Model):
    id = models.SlugField(primary_key=True, max_length=160)
    name = models.CharField(max_length=120)
    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name="tehsils"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tribe(models.Model):
    id = models.SlugField(primary_key=True, max_length=220)
    name = models.CharField(max_length=160)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    level = models.PositiveSmallIntegerField()
    level_name = models.CharField(max_length=40)
    pashto = models.CharField(max_length=160, blank=True)
    country = models.CharField(max_length=40)
    aliases = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Language(models.Model):
    id = models.SlugField(primary_key=True, max_length=80)
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Suggestion(models.Model):
    """Review queue for entries contributors add through the wizard's
    "can't find it? add yours" flow."""

    KIND_CHOICES = [
        ("province", "province"),
        ("district", "district"),
        ("tehsil", "tehsil"),
        ("tribe", "tribe"),
        ("language", "language"),
    ]
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("approved", "approved"),
        ("merged", "merged"),
        ("rejected", "rejected"),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    name = models.CharField(max_length=160)
    normalized_name = models.CharField(max_length=160)
    parent_id = models.CharField(max_length=220, blank=True)
    parent_name = models.CharField(max_length=160, blank=True)
    suggested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="suggestions",
    )
    times_suggested = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    merge_into = models.ForeignKey(
        Tribe,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="For the merge action: the existing tribe this duplicates.",
    )
    resolved_ref_id = models.CharField(max_length=220, blank=True)
    note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_suggestions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "normalized_name", "parent_id"],
                name="unique_suggestion_per_parent",
            ),
        ]

    def __str__(self):
        return f"{self.kind}: {self.name}"


class TribeDistrict(models.Model):
    ROLE_CHOICES = [("dominant", "dominant"), ("present", "present")]

    tribe = models.ForeignKey(
        Tribe, on_delete=models.CASCADE, related_name="district_links"
    )
    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name="tribe_links"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tribe", "district"], name="unique_tribe_district"
            ),
        ]

    def __str__(self):
        return f"{self.tribe} · {self.district} ({self.role})"
