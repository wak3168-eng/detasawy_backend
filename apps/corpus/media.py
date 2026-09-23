import mimetypes
import re

from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.identity.models import Profile
from .models import Contribution, Prompt


def file_response(request, field, private=True):
    try:
        stream = field.open("rb")
        size = field.size
    except (FileNotFoundError, OSError, ValueError):
        raise Http404 from None
    mime = mimetypes.guess_type(field.name)[0] or "application/octet-stream"
    if not mime.startswith(("audio/", "image/")) or mime == "image/svg+xml":
        mime = "application/octet-stream"
    range_header = request.headers.get("Range")
    if range_header:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
        start, end = 0, size - 1
        valid = bool(match and any(match.groups()) and size)
        if valid:
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(int(right), size - 1) if right else size - 1
            else:
                start = max(0, size - int(right))
            valid = 0 <= start <= end < size
        if not valid:
            stream.close()
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{size}"
        else:
            stream.seek(start)
            def chunks():
                remaining = end - start + 1
                try:
                    while remaining:
                        chunk = stream.read(min(65536, remaining))
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
                finally:
                    stream.close()
            response = StreamingHttpResponse(chunks(), status=206, content_type=mime)
            response["Content-Length"] = str(end - start + 1)
            response["Content-Range"] = f"bytes {start}-{end}/{size}"
    else:
        response = FileResponse(stream, content_type=mime)
    response["Accept-Ranges"] = "bytes"
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store" if private else "public, max-age=300"
    return response


@extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY, (206, "application/octet-stream"): OpenApiTypes.BINARY})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def contribution_audio(request, pk):
    rows = Contribution.objects.all()
    if not request.user.is_superuser:
        rows = rows.filter(contributor=request.user)
    row = get_object_or_404(rows, pk=pk)
    if not row.audio:
        raise Http404
    return file_response(request, row.audio)


@extend_schema(responses={(200, "image/webp"): OpenApiTypes.BINARY})
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def profile_photo(request, pk):
    rows = Profile.objects.select_related("photo_blob")
    if not request.user.is_superuser:
        rows = rows.filter(user=request.user)
    row = get_object_or_404(rows, user_id=pk)
    if not row.photo_blob_id:
        raise Http404
    response = HttpResponse(bytes(row.photo_blob.data), content_type=row.photo_blob.mime)
    response["Cache-Control"] = "private, no-store"
    return response


@extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
@api_view(["GET"])
@permission_classes([AllowAny])
def prompt_media(request, pk):
    row = get_object_or_404(Prompt, pk=pk)
    if not row.media or Contribution.objects.filter(audio=row.media.name).exists():
        raise Http404
    return file_response(request, row.media, private=False)


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
def legacy_prompt_media(request, path):
    # Query the model rather than joining untrusted input to MEDIA_ROOT.
    row = Prompt.objects.filter(media=path).first()
    if not row or not row.media or Contribution.objects.filter(audio=path).exists():
        raise Http404
    return file_response(request, row.media, private=False)
