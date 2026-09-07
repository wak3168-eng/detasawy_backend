import hashlib
import re
import unicodedata

CHAR_MAP = {"ك": "ک", "ي": "ی", "ى": "ی", "ة": "ه"}


def normalize_name(value: str) -> str:
    """Mirror of the frontend's nameMatch normalization: script unification,
    invisible-character stripping, case and whitespace folding."""
    value = unicodedata.normalize("NFC", value or "")
    value = re.sub(r"[​-‏ـ]", "", value)
    value = "".join(CHAR_MAP.get(c, c) for c in value)
    value = value.lower()
    value = re.sub(r"[^\w\s-]", " ", value)
    return re.sub(r"[\s\-_]+", " ", value).strip()


def slug_part(value: str) -> str:
    ascii_form = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_form).strip("-")
    if slug:
        return slug
    digest = hashlib.sha1(normalize_name(value).encode("utf-8")).hexdigest()[:8]
    return f"s{digest}"


def unique_ref_id(model, base: str) -> str:
    candidate = base
    suffix = 2
    while model.objects.filter(id=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate
