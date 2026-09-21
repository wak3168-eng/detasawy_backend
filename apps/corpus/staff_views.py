import os
import re

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from django.db.models import Count, Q
from rest_framework.permissions import BasePermission

from apps.corpus.aggregate import group_words
from apps.corpus.images import store_image
from apps.corpus.models import Contribution, Prompt
from apps.identity.permissions import IsContentManager
from apps.corpus.admin_serializers import DatasetQuery, ListQuery, PromptInput, list_page


def serialize_prompt(prompt, request):
    return {
        "id": prompt.id,
        "kind": prompt.kind,
        "mediaUrl": prompt.resolve_media_url(request),
        "captionEn": prompt.caption_en or None,
        "captionPs": prompt.caption_ps or None,
        "active": prompt.active,
        "servedCount": prompt.served_count,
        "licence": prompt.licence or None,
        "sourceUrl": prompt.source_url or None,
        "answers": getattr(prompt, "answers", 0),
        "createdAt": prompt.created_at.isoformat(),
    }


@api_view(["GET", "POST"])
@permission_classes([IsContentManager])
def staff_prompts(request):
    if request.method == "GET":
        query = ListQuery(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        rows = Prompt.objects.select_related("blob").annotate(answers=Count("contributions")).order_by("-created_at", "-id")
        if params.get("q"):
            rows = rows.filter(Q(caption_en__icontains=params["q"]) | Q(caption_ps__icontains=params["q"]))
        if params.get("kind"):
            rows = rows.filter(kind=params["kind"])
        if params.get("active"):
            rows = rows.filter(active=params["active"] == "true")
        if "page" not in request.query_params:
            return Response([serialize_prompt(p, request) for p in rows[:50]])
        return Response(list_page(rows, params, lambda p: serialize_prompt(p, request)))

    serializer = PromptInput(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    kind = data["kind"]
    if kind not in ("picture", "scene", "voice"):
        return Response(
            {"error": "kind must be picture, scene or voice"}, status=400,
        )
    media = request.FILES.get("media")
    media_url = data.get("mediaUrl", "")
    if not media and not media_url:
        return Response({"error": "a media file or mediaUrl is required"}, status=400)
    blob = None
    if media:
        expected = "audio/" if kind == "voice" else "image/"
        if not (media.content_type or "").startswith(expected):
            return Response(
                {"error": f"a {kind} prompt needs a {expected}* file"}, status=400,
            )
        if kind in ("picture", "scene"):
            # pictures live as DB blobs so they survive redeploys
            try:
                blob = store_image(media.read())
            except Exception:
                return Response(
                    {"error": "that image file can't be read"}, status=400,
                )

    prompt = Prompt.objects.create(
        kind=kind,
        blob=blob,
        media=None if blob else media,
        media_url=media_url[:500],
        source_url=data.get("sourceUrl", ""),
        licence=data.get("licence", ""),
        caption_en=data.get("captionEn", ""),
        caption_ps=data.get("captionPs", ""),
        created_by=request.user,
    )
    return Response(serialize_prompt(prompt, request), status=201)


@api_view(["POST"])
@permission_classes([IsContentManager])
def staff_prompt_update(request, pk):
    try:
        prompt = Prompt.objects.get(pk=pk)
    except Prompt.DoesNotExist:
        return Response({"error": "not found"}, status=404)
    active = request.data.get("active")
    if not isinstance(active, bool):
        return Response({"error": "active must be true or false"}, status=400)
    prompt.active = active
    prompt.save(update_fields=["active"])
    return Response(serialize_prompt(prompt, request))


def caption_from_filename(name):
    """A folder of photos names itself: apple.png -> apple,
    Red_Dahlia.jpg -> red dahlia."""
    stem = os.path.splitext(os.path.basename(name))[0]
    stem = re.sub(r"[_-]+", " ", stem)
    return re.sub(r"\s+", " ", stem).strip().lower()[:160]


@api_view(["POST"])
@permission_classes([IsContentManager])
def staff_prompts_batch(request):
    """Upload a whole folder at once. Each file's name becomes its caption,
    and anything already carrying that caption is left alone."""
    kind = request.data.get("kind")
    if kind not in ("picture", "scene", "voice"):
        return Response(
            {"error": "kind must be picture, scene or voice"}, status=400,
        )
    files = request.FILES.getlist("media")
    if not files:
        return Response({"error": "choose a folder of files first"}, status=400)

    expected = "audio/" if kind == "voice" else "image/"
    taken = {
        c.lower()
        for c in Prompt.objects.filter(kind=kind).values_list("caption_en", flat=True)
    }
    created, skipped, failed = [], [], []

    for upload in files:
        if not upload.size or upload.size > 20 * 1024 * 1024:
            failed.append({"name": upload.name, "why": "file must be non-empty and at most 20 MB"})
            continue
        caption = caption_from_filename(upload.name)
        if not caption:
            failed.append({"name": upload.name, "why": "no name to read"})
            continue
        if caption in taken:
            skipped.append(caption)
            continue
        if not (upload.content_type or "").startswith(expected):
            failed.append({"name": upload.name, "why": f"not a {expected[:-1]} file"})
            continue
        blob = None
        if kind in ("picture", "scene"):
            try:
                blob = store_image(upload.read())
            except Exception:
                failed.append({"name": upload.name, "why": "could not be read"})
                continue
        prompt = Prompt.objects.create(
            kind=kind,
            blob=blob,
            media=None if blob else upload,
            caption_en=caption,
            created_by=request.user,
        )
        taken.add(caption)
        created.append(serialize_prompt(prompt, request))

    return Response(
        {
            "created": created,
            "createdCount": len(created),
            "skipped": skipped,
            "failed": failed,
        },
        status=201 if created else 200,
    )


class IsSuperUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)


@api_view(["GET"])
@permission_classes([IsSuperUser])
def dataset(request):
    """The collection itself: every picture beside the words people gave it."""
    validation = DatasetQuery(data=request.query_params)
    validation.is_valid(raise_exception=True)
    params = validation.validated_data
    query = params.get("q", "")
    show_all = params["all"] == "1"
    limit, offset = params["limit"], params["offset"]

    prompts = Prompt.objects.annotate(
        answers=Count("contributions", distinct=True),
        voices=Count(
            "contributions",
            filter=Q(contributions__audio__isnull=False) & ~Q(contributions__audio=""),
            distinct=True,
        ),
    )
    if query:
        prompts = prompts.filter(Q(caption_en__icontains=query) | Q(caption_ps__icontains=query))
    if not show_all:
        prompts = prompts.filter(answers__gt=0)
    prompts = prompts.order_by("-answers", "caption_en", "id")

    total = prompts.count()
    page = list(prompts.select_related("blob")[offset:offset + limit])

    # one query for every contribution on this page, grouped in memory
    by_prompt = {}
    for row in Contribution.objects.filter(prompt__in=page):
        by_prompt.setdefault(row.prompt_id, []).append(row)

    items = [
        {
            "id": p.id,
            "kind": p.kind,
            "caption": p.caption_en or f"#{p.id}",
            "mediaUrl": p.resolve_media_url(request),
            "answers": p.answers,
            "voices": p.voices,
            "words": group_words(by_prompt.get(p.id, [])),
        }
        for p in page
    ]
    return Response({"total": total, "items": items})


@api_view(["GET"])
@permission_classes([IsSuperUser])
def staff_contributions(request):
    query = ListQuery(data=request.query_params)
    query.is_valid(raise_exception=True)
    params = query.validated_data
    rows = Contribution.objects.select_related("prompt", "prompt__blob").order_by("-updated_at", "-id")
    if params.get("q"):
        rows = rows.filter(Q(text_raw__icontains=params["q"]) | Q(prompt__caption_en__icontains=params["q"]))
    if params.get("kind"):
        rows = rows.filter(prompt__kind=params["kind"])
    if params.get("prompt"):
        rows = rows.filter(prompt_id=params["prompt"])
    has_audio = Q(audio__isnull=False) & ~Q(audio="")
    if params.get("audio"):
        rows = rows.filter(has_audio if params["audio"] == "yes" else ~has_audio)
    def serialize(row):
        district = row.district if isinstance(row.district, dict) else {}
        return {"id": row.id, "promptId": row.prompt_id,
                "caption": row.prompt.caption_en or f"Prompt {row.prompt_id}",
                "kind": row.prompt.kind, "mediaUrl": row.prompt.resolve_media_url(request),
                "text": row.text_raw, "audioUrl": request.build_absolute_uri(row.audio.url) if row.audio else None,
                "district": district.get("name") if isinstance(district.get("name"), str) else None,
                "createdAt": row.created_at.isoformat(), "updatedAt": row.updated_at.isoformat()}
    response = Response(list_page(rows, params, serialize))
    response["Cache-Control"] = "private, no-store"
    return response
