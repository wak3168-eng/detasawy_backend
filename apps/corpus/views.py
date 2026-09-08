import random
from collections import defaultdict
from datetime import timedelta

from django.http import Http404, HttpResponse, HttpResponseNotModified
from django.utils import timezone
from django.db.models import F
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.corpus.models import Contribution, MediaBlob, Prompt
from apps.corpus.wordcluster import cluster
from apps.identity.models import Profile
from apps.ref.normalize import normalize_name

# how long a prompt rests for someone after they answer it
REPEAT_AFTER_DAYS = 10


@extend_schema(
    parameters=[
        OpenApiParameter(
            "kind", str, required=True, enum=["picture", "scene", "voice"],
        ),
        OpenApiParameter("count", int, required=False),
    ],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def prompts(request):
    kind = request.GET.get("kind")
    if kind not in ("picture", "scene", "voice"):
        return Response(
            {"error": "kind must be picture, scene or voice"}, status=400,
        )
    try:
        count = max(1, min(int(request.GET.get("count", 1)), 10))
    except ValueError:
        count = 1

    pool = Prompt.objects.filter(kind=kind, active=True)
    # don't hand someone back a prompt they answered in the last ten days
    seen = Contribution.objects.filter(
        contributor=request.user,
        updated_at__gte=timezone.now() - timedelta(days=REPEAT_AFTER_DAYS),
    ).values_list("prompt_id", flat=True)
    ids = list(pool.exclude(id__in=seen).values_list("id", flat=True))
    if not ids:
        # they have worked through everything — let the oldest come round again
        ids = list(pool.values_list("id", flat=True))
    chosen = random.sample(ids, min(count, len(ids)))
    rows = Prompt.objects.filter(id__in=chosen).select_related("blob")
    Prompt.objects.filter(id__in=chosen).update(
        served_count=F("served_count") + 1,
    )

    data = []
    for row in rows:
        item = {
            "id": row.id,
            "kind": row.kind,
            "mediaUrl": row.resolve_media_url(request),
        }
        if row.caption_en:
            item["captionEn"] = row.caption_en
        if row.caption_ps:
            item["captionPs"] = row.caption_ps
        if row.source_url:
            item["sourceUrl"] = row.source_url
        if row.licence:
            item["licence"] = row.licence
        data.append(item)
    random.shuffle(data)

    response = Response(data)
    response["Cache-Control"] = "no-store"
    return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def contribute(request):
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None or not profile.completed_at:
        return Response(
            {"error": "Complete your profile before contributing."}, status=403,
        )

    prompt_id = request.data.get("prompt")
    text = (request.data.get("text") or "").strip()
    audio = request.FILES.get("audio")
    try:
        prompt = Prompt.objects.get(id=prompt_id, active=True)
    except (Prompt.DoesNotExist, ValueError, TypeError):
        return Response({"error": "unknown prompt"}, status=400)

    if prompt.kind == "scene":
        # a scene is spoken about; writing it down is a bonus
        if audio is None:
            return Response({"error": "record your voice to answer"}, status=400)
    elif not text:
        return Response({"error": "text is required"}, status=400)

    contribution, _ = Contribution.objects.update_or_create(
        prompt=prompt,
        contributor=request.user,
        defaults={
            "text_raw": text[:200],
            "text_norm": normalize_name(text)[:200],
            "district": profile.district,
            "tribe_path": profile.tribe_path or [],
            "language": profile.language or "",
        },
    )
    if audio:
        contribution.audio = audio
        contribution.save(update_fields=["audio"])

    today = timezone.localdate()
    today_count = Contribution.objects.filter(
        contributor=request.user, created_at__date=today,
    ).count()
    return Response({"id": contribution.id, "todayCount": today_count}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def today(request):
    count = Contribution.objects.filter(
        contributor=request.user, created_at__date=timezone.localdate(),
    ).count()
    return Response({"count": count})


def blob(request, sha):
    """Serve DB-stored prompt media. Content-addressed, so the response is
    immutable and cached hard by browsers."""
    etag = f'"{sha}"'
    if request.headers.get("If-None-Match") == etag:
        response = HttpResponseNotModified()
    else:
        try:
            row = MediaBlob.objects.get(sha256=sha)
        except MediaBlob.DoesNotExist:
            raise Http404 from None
        response = HttpResponse(bytes(row.data), content_type=row.mime)
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["ETag"] = etag
    return response


@api_view(["GET"])
@permission_classes([AllowAny])
def prompt_words(request, pk):
    rows = list(Contribution.objects.filter(prompt_id=pk))

    # spellings of one word travel together; different words stay apart
    clusters = cluster(row.text_norm for row in rows)
    key_of = {}
    for group in clusters:
        key = min(group)
        for form in group:
            key_of[form] = key

    grouped = defaultdict(
        lambda: {
            "count": 0,
            "display": defaultdict(int),
            "cells": defaultdict(int),
        },
    )
    for row in rows:
        entry = grouped[key_of.get(row.text_norm, row.text_norm)]
        entry["count"] += 1
        entry["display"][row.text_raw] += 1
        district = (row.district or {}).get("name") or "—"
        tribe_path = [t.get("name") for t in (row.tribe_path or []) if isinstance(t, dict)]
        tribe = tribe_path[0] if tribe_path else "—"
        clan = tribe_path[1] if len(tribe_path) > 1 else ""
        entry["cells"][(district, tribe, clan)] += 1

    data = []
    for entry in grouped.values():
        spellings = sorted(entry["display"].items(), key=lambda kv: -kv[1])
        data.append(
            {
                "word": spellings[0][0],
                "count": entry["count"],
                # every other way people wrote the same word, most used first
                "variants": [
                    {"word": word, "count": n} for word, n in spellings[1:]
                ],
                "rows": [
                    {"district": d, "tribe": t, "clan": c or None, "count": n}
                    for (d, t, c), n in sorted(
                        entry["cells"].items(), key=lambda kv: -kv[1],
                    )
                ],
            },
        )
    data.sort(key=lambda item: -item["count"])

    response = Response(data)
    response["Cache-Control"] = "public, s-maxage=30, stale-while-revalidate=120"
    return response
