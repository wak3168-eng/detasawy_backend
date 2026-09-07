from django.contrib.auth.models import Group
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.identity.models import User
from apps.identity.serializers import UserSerializer


class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


def serialize_row(user):
    data = UserSerializer(user).data
    data["joined"] = user.date_joined.date().isoformat()
    profile = getattr(user, "profile", None)
    data["profileComplete"] = bool(profile and profile.completed_at)
    return data


@extend_schema(parameters=[OpenApiParameter("q", str, required=False)])
@api_view(["GET"])
@permission_classes([IsSuperUser])
def users(request):
    query = (request.GET.get("q") or "").strip()
    rows = User.objects.select_related("profile").order_by("-date_joined")
    if query:
        rows = rows.filter(Q(email__icontains=query) | Q(name__icontains=query))
    return Response([serialize_row(u) for u in rows[:20]])


@api_view(["POST"])
@permission_classes([IsSuperUser])
def set_role(request):
    email = (request.data.get("email") or "").strip().lower()
    role = request.data.get("role")
    if role not in ("reviewer", "contributor"):
        return Response({"error": "role must be reviewer or contributor"}, status=400)
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return Response({"error": "no account with that email"}, status=404)
    if user.is_superuser:
        return Response({"error": "superadmin roles can't be changed here"}, status=400)

    group, _ = Group.objects.get_or_create(name="Reviewers")
    if role == "reviewer":
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        user.groups.add(group)
    else:
        user.is_staff = False
        user.save(update_fields=["is_staff"])
        user.groups.remove(group)
    return Response(serialize_row(user))
