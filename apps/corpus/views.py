import random

from django.db.models import F
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.corpus.models import Prompt


@extend_schema(
    parameters=[
        OpenApiParameter("kind", str, required=True, enum=["picture", "voice"]),
        OpenApiParameter("count", int, required=False),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def prompts(request):
    kind = request.GET.get("kind")
    if kind not in ("picture", "voice"):
        return Response({"error": "kind must be picture or voice"}, status=400)
    try:
        count = max(1, min(int(request.GET.get("count", 1)), 10))
    except ValueError:
        count = 1

    ids = list(
        Prompt.objects.filter(kind=kind, active=True).values_list("id", flat=True),
    )
    chosen = random.sample(ids, min(count, len(ids)))
    rows = Prompt.objects.filter(id__in=chosen)
    Prompt.objects.filter(id__in=chosen).update(
        served_count=F("served_count") + 1,
    )

    data = []
    for row in rows:
        item = {
            "id": row.id,
            "kind": row.kind,
            "mediaUrl": request.build_absolute_uri(row.media.url),
        }
        if row.caption_en:
            item["captionEn"] = row.caption_en
        if row.caption_ps:
            item["captionPs"] = row.caption_ps
        data.append(item)
    random.shuffle(data)

    response = Response(data)
    response["Cache-Control"] = "no-store"
    return response
