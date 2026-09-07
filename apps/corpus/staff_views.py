from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.corpus.images import store_image
from apps.corpus.models import Prompt
from apps.identity.permissions import IsContentManager


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
        "createdAt": prompt.created_at.isoformat(),
    }


@api_view(["GET", "POST"])
@permission_classes([IsContentManager])
def staff_prompts(request):
    if request.method == "GET":
        rows = Prompt.objects.select_related("blob")[:50]
        return Response([serialize_prompt(p, request) for p in rows])

    kind = request.data.get("kind")
    if kind not in ("picture", "voice"):
        return Response({"error": "kind must be picture or voice"}, status=400)
    media = request.FILES.get("media")
    media_url = (request.data.get("mediaUrl") or "").strip()
    if not media and not media_url:
        return Response({"error": "a media file or mediaUrl is required"}, status=400)
    blob = None
    if media:
        expected = "image/" if kind == "picture" else "audio/"
        if not (media.content_type or "").startswith(expected):
            return Response(
                {"error": f"a {kind} prompt needs a {expected}* file"}, status=400,
            )
        if kind == "picture":
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
        source_url=(request.data.get("sourceUrl") or "").strip()[:500],
        licence=(request.data.get("licence") or "").strip()[:200],
        caption_en=(request.data.get("captionEn") or "").strip()[:160],
        caption_ps=(request.data.get("captionPs") or "").strip()[:160],
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
