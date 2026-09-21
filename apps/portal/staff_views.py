from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.identity.permissions import IsContentManager
from apps.portal.models import Campaign
from apps.ref.models import District, Province
from rest_framework import serializers


def serialize_campaign(campaign):
    now = timezone.now()
    if campaign.ends_at <= now:
        status = "ended"
    elif campaign.starts_at > now:
        status = "upcoming"
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
    try:
        dt = parse_datetime(str(value or ""))
    except (ValueError, TypeError):
        return None
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

    class Input(serializers.Serializer):
        name = serializers.CharField(max_length=120)
        description = serializers.CharField(max_length=200, required=False, allow_blank=True)
        scopeType = serializers.ChoiceField(choices=["all", "district", "province"], default="all")
        scopeId = serializers.CharField(max_length=120, required=False, allow_blank=True)
    validation = Input(data=request.data)
    validation.is_valid(raise_exception=True)
    data = validation.validated_data
    name = data["name"]
    if not name:
        return Response({"error": "name is required"}, status=400)
    scope_type = data["scopeType"]
    if scope_type not in ("all", "district", "province"):
        return Response({"error": "invalid scope"}, status=400)
    starts_at = _parse_dt(request.data.get("startsAt"))
    ends_at = _parse_dt(request.data.get("endsAt"))
    if not starts_at or not ends_at or ends_at <= starts_at:
        return Response({"error": "valid start and end dates are required"}, status=400)

    scope_id, scope_name = "", ""
    if scope_type != "all":
        model = District if scope_type == "district" else Province
        scope = model.objects.filter(pk=data.get("scopeId", "")).first()
        if scope is None:
            return Response({"error": "Select a valid scope."}, status=400)
        scope_id, scope_name = scope.pk, scope.name

    campaign = Campaign.objects.create(
        name=name[:120],
        description=data.get("description", ""),
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
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
