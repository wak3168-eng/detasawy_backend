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

from datetime import timedelta

from django.utils import timezone

from apps.corpus.models import Contribution, Prompt
from apps.identity.models import Profile, User
from apps.portal.models import Campaign
from apps.ref.models import Language, Suggestion, Tribe
from apps.ref.services import (
    approve_suggestion,
    keep_suggestion,
    merge_suggestion,
    reject_suggestion,
    sibling_candidates,
)


def serialize_suggestion(suggestion):
    live = (
        suggestion.status == "approved"
        and bool(suggestion.resolved_ref_id)
        and suggestion.reviewed_by_id is None
    )
    return {
        "id": suggestion.id,
        "kind": suggestion.kind,
        "name": suggestion.name,
        "parentId": suggestion.parent_id or None,
        "parentName": suggestion.parent_name or None,
        "timesSuggested": suggestion.times_suggested,
        "suggestedBy": suggestion.suggested_by.email if suggestion.suggested_by else None,
        "status": suggestion.status,
        "live": live,
        "resolvedRefId": suggestion.resolved_ref_id or None,
        "createdAt": suggestion.created_at.isoformat(),
        "candidates": sibling_candidates(suggestion),
        "mergeIntoId": suggestion.merge_into_id or None,
        "mergeIntoName": suggestion.merge_into.name if suggestion.merge_into else None,
    }


@api_view(["GET"])
@permission_classes([IsAdminUser])
def overview(request):
    now = timezone.now()
    contributions = Contribution.objects.all()
    return Response(
        {
            # the dataset itself
            "uniqueWords": contributions.values("text_norm").distinct().count(),
            "pictures": Prompt.objects.filter(kind="picture").count(),
            "picturesActive": Prompt.objects.filter(
                kind="picture", active=True,
            ).count(),
            "picturesAnswered": contributions.values("prompt_id")
            .distinct()
            .count(),
            "contributions": contributions.count(),
            "contributionsToday": contributions.filter(
                created_at__date=timezone.localdate(),
            ).count(),
            "contributionsWeek": contributions.filter(
                created_at__gte=now - timedelta(days=7),
            ).count(),
            "voiceNotes": contributions.exclude(audio="")
            .exclude(audio__isnull=True)
            .count(),
            # the community
            "users": User.objects.count(),
            "profilesCompleted": Profile.objects.exclude(completed_at=None).count(),
            "contributors": contributions.values("contributor_id")
            .distinct()
            .count(),
            "districtsCovered": contributions.exclude(district__isnull=True)
            .values("district__id")
            .distinct()
            .count(),
            # operations
            "campaignsLive": Campaign.objects.filter(
                starts_at__lte=now, ends_at__gte=now,
            ).count(),
            "suggestionsPending": Suggestion.objects.filter(
                status="pending",
            ).count(),
            "tribes": Tribe.objects.count(),
            "languages": Language.objects.count(),
        },
    )


@extend_schema(parameters=[OpenApiParameter("status", str, required=False)])
@api_view(["GET"])
@permission_classes([IsReviewer])
def suggestions(request):
    status = request.GET.get("status", "review")
    if status in ("review", "pending"):
        # everything a human still needs to look at: legacy pending entries
        # plus auto-published ones nobody has reviewed
        from django.db.models import Q

        rows = Suggestion.objects.filter(
            Q(status="pending")
            | Q(status="approved", reviewed_by__isnull=True, resolved_ref_id__gt=""),
        )
    else:
        rows = Suggestion.objects.filter(status=status)
    rows = rows.order_by("-times_suggested", "-created_at")[:50]
    return Response([serialize_suggestion(s) for s in rows])


@api_view(["POST"])
@permission_classes([IsReviewer])
def suggestion_action(request, pk):
    try:
        suggestion = Suggestion.objects.get(pk=pk)
    except Suggestion.DoesNotExist:
        return Response({"error": "not found"}, status=404)

    action = request.data.get("action")
    try:
        if action == "approve":
            approve_suggestion(suggestion, request.user)
        elif action == "keep":
            keep_suggestion(suggestion, request.user)
        elif action == "reject":
            reject_suggestion(suggestion, request.user)
        elif action == "merge":
            target_id = request.data.get("mergeIntoId")
            suggestion.merge_into = Tribe.objects.filter(id=target_id).first()
            merge_suggestion(suggestion, request.user)
        else:
            return Response(
                {"error": "action must be approve, keep, reject or merge"},
                status=400,
            )
    except ValueError as error:
        return Response({"error": str(error)}, status=400)

    return Response(serialize_suggestion(suggestion))
