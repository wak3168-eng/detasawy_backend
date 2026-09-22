from rest_framework import serializers
from django.core.validators import RegexValidator


class ListQuery(serializers.Serializer):
    page = serializers.IntegerField(min_value=1, default=1)
    pageSize = serializers.IntegerField(min_value=1, max_value=50, default=20)
    q = serializers.CharField(required=False, allow_blank=True, max_length=200)
    kind = serializers.ChoiceField(choices=["picture", "scene", "voice"], required=False)
    active = serializers.ChoiceField(choices=["true", "false"], required=False)
    audio = serializers.ChoiceField(choices=["yes", "no"], required=False)
    prompt = serializers.IntegerField(min_value=1, required=False)


def list_page(rows, params, serialize):
    page, size = params["page"], params["pageSize"]
    start = (page - 1) * size
    return {"items": [serialize(row) for row in rows[start:start + size]],
            "total": rows.count(), "page": page, "pageSize": size}


class PromptInput(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["picture", "scene", "voice"])
    media = serializers.FileField(required=False)
    mediaUrl = serializers.URLField(required=False, allow_blank=True, max_length=500,
                                   validators=[RegexValidator(r"^https?://", "Use an HTTP or HTTPS URL.")])
    sourceUrl = serializers.URLField(required=False, allow_blank=True, max_length=500,
                                    validators=[RegexValidator(r"^https?://", "Use an HTTP or HTTPS URL.")])
    licence = serializers.CharField(required=False, allow_blank=True, max_length=200)
    captionEn = serializers.CharField(required=False, allow_blank=True, max_length=160)
    captionPs = serializers.CharField(required=False, allow_blank=True, max_length=160)

    def validate(self, attrs):
        if not attrs.get("media") and not attrs.get("mediaUrl"):
            raise serializers.ValidationError("A file or media URL is required.")
        if attrs.get("media") and attrs.get("mediaUrl"):
            raise serializers.ValidationError("Choose a file or a media URL, not both.")
        media = attrs.get("media")
        if media and media.size > 20 * 1024 * 1024:
            raise serializers.ValidationError("Files must be at most 20 MB.")
        return attrs


class DatasetQuery(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=200)
    all = serializers.ChoiceField(choices=["0", "1"], default="0")
    groupBy = serializers.ChoiceField(
        choices=["all", "country", "province", "district", "tehsil", "tribe", "clan", "subclan"],
        default="all",
    )
    group = serializers.CharField(required=False, allow_blank=True, max_length=220)
    minSample = serializers.IntegerField(min_value=1, max_value=100, default=10)
    limit = serializers.IntegerField(min_value=1, max_value=50, default=20)
    offset = serializers.IntegerField(min_value=0, default=0)
