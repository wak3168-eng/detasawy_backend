from django.contrib.auth import authenticate, login as start_session, logout as end_session
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from apps.identity.throttles import AuthThrottle

from apps.identity.models import Profile
from apps.identity.serializers import (
    CONSENT_VERSION,
    LoginSerializer,
    ProfileSerializer,
    SignupSerializer,
    UserSerializer,
)
from apps.identity.models import User


def session_payload(request, user):
    return {
        "csrfToken": get_token(request),
        "user": UserSerializer(user).data,
        "profile": ProfileSerializer(user.profile).data,
    }


@extend_schema(responses=inline_serializer(name="CsrfToken", fields={"csrfToken": serializers.CharField()}))
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"csrfToken": get_token(request)})


@extend_schema(request=SignupSerializer)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def signup(request):
    """Closed while the pilot is invitation-only: a superadmin creates the
    account instead (POST /api/admin/users/create)."""
    return Response(
        {"error": "Detasawy is invite-only for now. Ask the team for an account."},
        status=status.HTTP_403_FORBIDDEN,
    )


@extend_schema(request=LoginSerializer, responses=inline_serializer(name="CookieSession", fields={
    "csrfToken": serializers.CharField(), "user": UserSerializer(), "profile": ProfileSerializer(),
}))
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
    start_session(request._request, user)
    Token.objects.filter(user=user).delete()
    return Response(session_payload(request, user))


@extend_schema(request=None, responses={204: None})
@api_view(["POST"])
@permission_classes([AllowAny])
def logout(request):
    end_session(request._request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return Response(
        {
            "user": UserSerializer(request.user).data,
            "profile": ProfileSerializer(profile, context={"request": request}).data,
        },
    )


@extend_schema(request=ProfileSerializer)
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def profile(request):
    from apps.ref.services import capture_suggestions

    instance, _ = Profile.objects.get_or_create(user=request.user)
    serializer = ProfileSerializer(
        instance, data=request.data, partial=True, context={"request": request},
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    capture_suggestions(instance)
    # capture may have canonicalized spellings in place — return the final state
    return Response(ProfileSerializer(instance, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def profile_photo(request):
    """Store the profile photo as a database blob so it outlives the browser
    and every redeploy."""
    from apps.corpus.images import store_image

    upload = request.FILES.get("photo")
    if upload is None:
        return Response({"error": "photo file is required"}, status=400)
    if not (upload.content_type or "").startswith("image/"):
        return Response({"error": "that needs to be an image"}, status=400)
    try:
        blob = store_image(upload.read())
    except Exception:
        return Response({"error": "that image can't be read"}, status=400)

    instance, _ = Profile.objects.get_or_create(user=request.user)
    instance.photo_blob = blob
    instance.save(update_fields=["photo_blob", "updated_at"])
    return Response(
        ProfileSerializer(instance, context={"request": request}).data, status=201,
    )
