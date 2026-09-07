from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.identity.models import Profile, User

CONSENT_VERSION = "v0-pilot"


class SignupSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    consent = serializers.BooleanField()

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Consent is required to contribute.")
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["name", "email", "role"]

    def get_role(self, obj):
        if obj.is_superuser:
            return "superadmin"
        if obj.is_staff:
            return "reviewer"
        return "contributor"


class ProfileSerializer(serializers.ModelSerializer):
    tribePath = serializers.JSONField(source="tribe_path", required=False)
    completedAt = serializers.DateTimeField(
        source="completed_at", required=False, allow_null=True
    )

    class Meta:
        model = Profile
        fields = [
            "country",
            "province",
            "district",
            "tehsil",
            "city",
            "tribePath",
            "language",
            "completedAt",
        ]
