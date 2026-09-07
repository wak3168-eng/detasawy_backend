from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.identity.permissions import IsContentManager
from apps.portal.models import Campaign


def serialize_campaign(campaign):
    now = timezone.now()
    if campaign.starts_at > now:
        status = "upcoming"
    elif campaign.ends_at < now:
        status = "ended"
    else:
        status = "live"
    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description or None,
        "scopeType": campaign.scope_type,
        "scopeName": campaign.scope_name or None,
        "startsAt": campaign.starts_at.isoformat(),
        "endsAt": campaign.ends_at.isoformat(),
        "status": status,
    }


def _parse_dt(value):
    dt = parse_datetime(str(value or ""))
    if dt is None:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


@api_view(["GET", "POST"])
@permission_classes([IsContentManager])
def staff_campaigns(request):
    if request.method == "GET":
        rows = Campaign.objects.order_by("-ends_at")[:30]
        return Response([serialize_campaign(c) for c in rows])

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"error": "name is required"}, status=400)
    scope_type = request.data.get("scopeType", "all")
    if scope_type not in ("all", "district", "province"):
        return Response({"error": "invalid scope"}, status=400)
    starts_at = _parse_dt(request.data.get("startsAt"))
    ends_at = _parse_dt(request.data.get("endsAt"))
    if not starts_at or not ends_at or ends_at <= starts_at:
        return Response({"error": "valid start and end dates are required"}, status=400)

    campaign = Campaign.objects.create(
        name=name[:120],
        description=(request.data.get("description") or "").strip()[:200],
        scope_type=scope_type,
        scope_id=(request.data.get("scopeId") or "")[:120],
        scope_name=(request.data.get("scopeName") or "")[:120],
        starts_at=starts_at,
        ends_at=ends_at,
        created_by=request.user,
    )
    return Response(serialize_campaign(campaign), status=201)


@api_view(["POST"])
@permission_classes([IsContentManager])
def staff_campaign_end(request, pk):
    try:
        campaign = Campaign.objects.get(pk=pk)
    except Campaign.DoesNotExist:
        return Response({"error": "not found"}, status=404)
    campaign.ends_at = timezone.now()
    campaign.save(update_fields=["ends_at"])
    return Response(serialize_campaign(campaign))
