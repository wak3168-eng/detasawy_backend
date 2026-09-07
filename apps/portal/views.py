from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.portal.models import Campaign


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
