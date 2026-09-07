from django.contrib.auth import authenticate
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.identity.models import Profile
from apps.identity.serializers import (
    CONSENT_VERSION,
    LoginSerializer,
    ProfileSerializer,
    SignupSerializer,
    UserSerializer,
)
from apps.identity.models import User


class AuthThrottle(ScopedRateThrottle):
    scope = "auth"


def session_payload(user, token):
    return {
        "token": token.key,
        "user": UserSerializer(user).data,
        "profile": ProfileSerializer(user.profile).data,
    }


@extend_schema(request=SignupSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def signup(request):
    serializer = SignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    user = User.objects.create_user(
        email=data["email"],
        password=data["password"],
        name=data["name"],
        consent_version=CONSENT_VERSION,
        consented_at=timezone.now(),
    )
    Profile.objects.create(user=user)
    token = Token.objects.create(user=user)
    return Response(session_payload(user, token), status=status.HTTP_201_CREATED)


@extend_schema(request=LoginSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = authenticate(
        request,
        username=serializer.validated_data["email"].lower(),
        password=serializer.validated_data["password"],
    )
    if user is None:
        return Response(
            {"error": "Invalid email or password."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    Profile.objects.get_or_create(user=user)
    token, _ = Token.objects.get_or_create(user=user)
    return Response(session_payload(user, token))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    request.auth.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return Response(
        {
            "user": UserSerializer(request.user).data,
            "profile": ProfileSerializer(profile).data,
        },
    )


@extend_schema(request=ProfileSerializer)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def profile(request):
    from apps.ref.services import capture_suggestions

    instance, _ = Profile.objects.get_or_create(user=request.user)
    serializer = ProfileSerializer(instance, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    capture_suggestions(instance)
    return Response(serializer.data)
