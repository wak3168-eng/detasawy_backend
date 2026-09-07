import hashlib
from io import BytesIO

from PIL import Image, ImageOps

from apps.corpus.models import MediaBlob

MAX_EDGE = 640
JPEG_QUALITY = 82


def store_image(raw: bytes) -> MediaBlob:
    """Re-encode an image as a small JPEG (max 640px, EXIF stripped and
    orientation applied) and persist it as a content-addressed DB blob."""
    img = Image.open(BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE))
    out = BytesIO()
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    data = out.getvalue()
    sha = hashlib.sha256(data).hexdigest()
    blob, _ = MediaBlob.objects.get_or_create(
        sha256=sha,
        defaults={"mime": "image/jpeg", "data": data, "size": len(data)},
    )
    return blob
