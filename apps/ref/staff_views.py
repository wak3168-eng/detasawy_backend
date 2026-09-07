from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAdminUser
from rest_framework.response import Response


class IsReviewer(BasePermission):
    """Superadmin, or a member of the Reviewers group."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.groups.filter(name="Reviewers").exists()),
        )

from apps.corpus.models import Prompt
from apps.identity.models import Profile, User
from apps.ref.models import Language, Suggestion, Tribe
from apps.ref.services import (
    approve_suggestion,
    merge_suggestion,
    reject_suggestion,
    sibling_candidates,
)


def serialize_suggestion(suggestion):
    return {
        "id": suggestion.id,
        "kind": suggestion.kind,
        "name": suggestion.name,
        "parentId": suggestion.parent_id or None,
        "parentName": suggestion.parent_name or None,
        "timesSuggested": suggestion.times_suggested,
        "suggestedBy": suggestion.suggested_by.email if suggestion.suggested_by else None,
        "status": suggestion.status,
        "resolvedRefId": suggestion.resolved_ref_id or None,
        "createdAt": suggestion.created_at.isoformat(),
        "candidates": sibling_candidates(suggestion),
    }


@api_view(["GET"])
@permission_classes([IsAdminUser])
def overview(request):
    return Response(
        {
            "users": User.objects.count(),
            "profilesCompleted": Profile.objects.exclude(completed_at=None).count(),
            "tribes": Tribe.objects.count(),
            "languages": Language.objects.count(),
            "suggestionsPending": Suggestion.objects.filter(status="pending").count(),
            "prompts": Prompt.objects.filter(active=True).count(),
        },
    )


@extend_schema(parameters=[OpenApiParameter("status", str, required=False)])
@api_view(["GET"])
@permission_classes([IsReviewer])
def suggestions(request):
    status = request.GET.get("status", "pending")
    rows = Suggestion.objects.filter(status=status).order_by("-times_suggested", "-created_at")[:50]
    return Response([serialize_suggestion(s) for s in rows])


@api_view(["POST"])
@permission_classes([IsReviewer])
def suggestion_action(request, pk):
    try:
        suggestion = Suggestion.objects.get(pk=pk)
    except Suggestion.DoesNotExist:
        return Response({"error": "not found"}, status=404)
    if suggestion.status != "pending":
        return Response({"error": "already resolved"}, status=400)

    action = request.data.get("action")
    try:
        if action == "approve":
            approve_suggestion(suggestion, request.user)
        elif action == "reject":
            reject_suggestion(suggestion, request.user)
        elif action == "merge":
            target_id = request.data.get("mergeIntoId")
            suggestion.merge_into = Tribe.objects.filter(id=target_id).first()
            merge_suggestion(suggestion, request.user)
        else:
            return Response({"error": "action must be approve, reject or merge"}, status=400)
    except ValueError as error:
        return Response({"error": str(error)}, status=400)

    return Response(serialize_suggestion(suggestion))
