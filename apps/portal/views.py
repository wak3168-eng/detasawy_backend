from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.corpus.models import Contribution, Prompt
from apps.identity.models import Profile
from apps.portal.models import Campaign
from apps.ref.models import Language, Tribe


@api_view(["GET"])
@permission_classes([AllowAny])
def campaigns(request):
    now = timezone.now()
    rows = Campaign.objects.filter(starts_at__lte=now, ends_at__gte=now)
    data = [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description or None,
            "scopeType": c.scope_type,
            "scopeName": c.scope_name or None,
            "startsAt": c.starts_at.isoformat(),
            "endsAt": c.ends_at.isoformat(),
        }
        for c in rows
    ]
    response = Response(data)
    response["Cache-Control"] = "public, s-maxage=60, stale-while-revalidate=300"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def public_stats(request):
    """Everything the landing page shows, in one live call."""
    contributions = Contribution.objects.all()
    written = contributions.exclude(text_norm="")

    # who is carrying the work right now — drives the map and the race
    top = (
        contributions.exclude(district__isnull=True)
        .values("district__id", "district__name")
        .annotate(words=Count("id"))
        .order_by("-words")[:12]
    )
    top_districts = [
        {
            "id": row["district__id"],
            "name": row["district__name"] or "Unknown",
            "words": row["words"],
        }
        for row in top
    ]

    # the newest words, for the line that scrolls under the numbers
    recent = []
    for row in written.select_related(None).order_by("-created_at")[:12]:
        place = (row.district or {}).get("name")
        tribe = next(
            (t.get("name") for t in (row.tribe_path or []) if isinstance(t, dict)),
            None,
        )
        recent.append(
            {"word": row.text_raw, "district": place, "tribe": tribe},
        )

    response = Response(
        {
            "contributors": Profile.objects.exclude(completed_at=None).count(),
            "uniqueWords": written.values("text_norm").distinct().count(),
            "words": written.count(),
            "voices": contributions.exclude(audio="").exclude(audio__isnull=True).count(),
            "pictures": Prompt.objects.filter(kind="picture", active=True).count(),
            "scenes": Prompt.objects.filter(kind="scene", active=True).count(),
            "districts": contributions.exclude(district__isnull=True)
            .values("district__id")
            .distinct()
            .count(),
            "tribes": Tribe.objects.count(),
            "languages": Language.objects.count(),
            "campaignsLive": Campaign.objects.filter(
                starts_at__lte=timezone.now(), ends_at__gte=timezone.now(),
            ).count(),
            "topDistricts": top_districts,
            "recent": recent,
        },
    )
    response["Cache-Control"] = "public, s-maxage=60, stale-while-revalidate=300"
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def district_leaderboard(request):
    rows = (
        Contribution.objects.exclude(district__isnull=True)
        .values("district__id", "district__name")
        .annotate(points=Count("id"))
        .order_by("-points")[:10]
    )
    data = [
        {
            "rank": index,
            "name": row["district__name"] or "Unknown",
            "points": row["points"],
        }
        for index, row in enumerate(rows, 1)
    ]
    response = Response(data)
    response["Cache-Control"] = "public, s-maxage=60, stale-while-revalidate=300"
    return response


def _streak(dates):
    """Consecutive daily streak ending today or yesterday."""
    today = timezone.localdate()
    if today not in dates and today - timedelta(days=1) not in dates:
        return 0
    day = today if today in dates else today - timedelta(days=1)
    streak = 0
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_stats(request):
    mine = Contribution.objects.filter(contributor=request.user)
    total = mine.count()
    today_count = mine.filter(created_at__date=timezone.localdate()).count()
    dates = {d.date() for d in mine.values_list("created_at", flat=True)}

    overall_rank = None
    district_rank = None
    if total:
        per_user = Contribution.objects.values("contributor").annotate(
            c=Count("id"),
        )
        overall_rank = sum(1 for row in per_user if row["c"] > total) + 1
        profile = Profile.objects.filter(user=request.user).first()
        district_id = (profile.district or {}).get("id") if profile else None
        if district_id:
            per_user_district = (
                Contribution.objects.filter(district__id=district_id)
                .values("contributor")
                .annotate(c=Count("id"))
            )
            my_here = mine.filter(district__id=district_id).count()
            district_rank = (
                sum(1 for row in per_user_district if row["c"] > my_here) + 1
            )

    return Response(
        {
            "points": total,
            "wordsAccepted": total,
            "todayCount": today_count,
            "streak": _streak(dates),
            "overallRank": overall_rank,
            "districtRank": district_rank,
        },
    )
