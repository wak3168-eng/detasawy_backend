from rest_framework import serializers


class RefOptionSerializer(serializers.Serializer):
    """Shape shared with the Next.js frontend (RefOption)."""

    id = serializers.CharField()
    name = serializers.CharField()
    ps = serializers.CharField(required=False)
    aliases = serializers.ListField(child=serializers.CharField(), required=False)
    hasChildren = serializers.BooleanField(required=False)
    hasTehsils = serializers.BooleanField(required=False)
    language = serializers.CharField(required=False)
