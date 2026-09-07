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


# Transliteration families of the generic lineage suffixes. Spellings within
# a family are the same word; Khel and Zai are NOT interchangeable.
SUFFIX_FAMILIES = {
    "khel": "khel", "khail": "khel", "kheil": "khel", "khell": "khel",
    "zai": "zai", "zay": "zai", "zi": "zai", "zey": "zai",
}


def split_generic_suffix(normalized: str) -> tuple[str, str]:
    """('sheikhmal khel') → ('sheikhmal', 'khel'); single words keep ''."""
    parts = normalized.split()
    if len(parts) > 1 and parts[-1] in SUFFIX_FAMILIES:
        return " ".join(parts[:-1]), SUFFIX_FAMILIES[parts[-1]]
    return normalized, ""


def names_equivalent(a: str, b: str) -> bool:
    """Same normalized name, tolerating a missing or differently spelled
    generic suffix of the SAME family (Sheikhmal ~ Sheikhmal Khel ~
    Sheikhmal Khail, but Adam Khel ≠ Adam Zai)."""
    if a == b:
        return True
    head_a, fam_a = split_generic_suffix(a)
    head_b, fam_b = split_generic_suffix(b)
    if head_a != head_b:
        return False
    return fam_a == fam_b or not fam_a or not fam_b


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
