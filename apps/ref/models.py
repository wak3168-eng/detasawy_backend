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
