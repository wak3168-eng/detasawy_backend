import difflib

from django.db.models import F
from django.utils import timezone

from apps.identity.models import Profile
from apps.ref.models import (
    District,
    Language,
    Province,
    Suggestion,
    Tehsil,
    Tribe,
)
from apps.ref.normalize import (
    names_equivalent,
    normalize_name,
    slug_part,
    split_generic_suffix,
    unique_ref_id,
)

LEVEL_NAMES = [
    "confederacy",
    "tribe",
    "clan",
    "division",
    "sub_division",
    "section",
    "minor_fraction",
]


def _entry(value):
    return value if isinstance(value, dict) else {}


def _sibling_rows(kind, parent_id):
    """Existing canonical rows a submitted name must be checked against."""
    if kind == "tribe":
        if parent_id:
            return Tribe.objects.filter(parent_id=parent_id)
        return Tribe.objects.filter(parent__isnull=True)
    if kind == "district":
        return District.objects.filter(province_id=parent_id)
    if kind == "tehsil":
        return Tehsil.objects.filter(district_id=parent_id)
    if kind == "province":
        return Province.objects.filter(country_id=parent_id)
    if kind == "language":
        return Language.objects.all()
    return []


def _row_names(row):
    names = []
    for name in [row.name, *(getattr(row, "aliases", None) or [])]:
        normalized = normalize_name(name)
        if normalized:
            names.append(normalized)
    return names


def _canonical_match(kind, normalized, parent_id):
    """The canonical row a submitted spelling exactly is — name or alias,
    tolerating a missing/same-family generic suffix (Khel ≠ Zai)."""
    for row in _sibling_rows(kind, parent_id):
        if any(names_equivalent(n, normalized) for n in _row_names(row)):
            return row
    return None


def _pair_ratio(a, b):
    best = difflib.SequenceMatcher(None, a, b).ratio()
    head_a, fam_a = split_generic_suffix(a)
    head_b, fam_b = split_generic_suffix(b)
    if fam_a == fam_b or not fam_a or not fam_b:
        best = max(best, difflib.SequenceMatcher(None, head_a, head_b).ratio())
    return best


def _fuzzy_candidates(kind, normalized, parent_id, limit=3, cutoff=0.75):
    """Near-spelling canonical rows, alias- and suffix-aware, best first."""
    scored = []
    for row in _sibling_rows(kind, parent_id):
        best = max(
            (_pair_ratio(n, normalized) for n in _row_names(row)), default=0.0,
        )
        if best >= cutoff:
            scored.append((best, row))
    scored.sort(key=lambda pair: -pair[0])
    return [row for _, row in scored[:limit]]


def _add_suggestion(user, kind, entry, parent_id, parent_name):
    """Returns (suggestions_created, canonical_row_if_auto_resolved).

    A spelling that exactly matches an existing sibling (name or alias,
    suffix-tolerant) never enters the queue — the entry is re-pointed to the
    canonical row on the spot. Near matches enter the queue pre-linked to
    their likely duplicate so review defaults to merge."""
    entry = _entry(entry)
    name = (entry.get("name") or "").strip()
    if not entry.get("pending") or not name:
        return 0, None
    normalized = normalize_name(name)
    if not normalized:
        return 0, None

    canonical = _canonical_match(kind, normalized, parent_id or "")
    if canonical is not None:
        entry["id"] = canonical.id
        entry["name"] = canonical.name
        entry.pop("pending", None)
        return 0, canonical

    suggestion, created = Suggestion.objects.get_or_create(
        kind=kind,
        normalized_name=normalized,
        parent_id=parent_id or "",
        defaults={
            "name": name,
            "parent_name": parent_name or "",
            "suggested_by": user,
        },
    )
    if created:
        if kind == "tribe" and suggestion.merge_into is None:
            near = _fuzzy_candidates(kind, normalized, parent_id or "", limit=1)
            if near:
                suggestion.merge_into = near[0]
                suggestion.save(update_fields=["merge_into"])
    else:
        Suggestion.objects.filter(
            kind=kind,
            normalized_name=normalized,
            parent_id=parent_id or "",
            status="pending",
        ).exclude(suggested_by=user).update(
            times_suggested=F("times_suggested") + 1,
        )
    return (1 if created else 0), None


def capture_suggestions(profile: Profile) -> int:
    """Resolve or queue every pending entry in a profile. Exact spellings of
    known entries are canonicalized immediately; the rest go to review."""
    user = profile.user
    country = _entry(profile.country)
    province = _entry(profile.province)
    district = _entry(profile.district)
    created = 0
    changed = set()

    for kind, entry, pid, pname in [
        ("province", profile.province, country.get("id"), country.get("name")),
        ("district", profile.district, province.get("id"), province.get("name")),
        ("tehsil", profile.tehsil, district.get("id"), district.get("name")),
    ]:
        n, resolved = _add_suggestion(user, kind, entry, pid, pname)
        created += n
        if resolved is not None:
            changed.add(kind)

    parent_id = ""
    parent_name = ""
    for node in profile.tribe_path or []:
        node = _entry(node)
        n, resolved = _add_suggestion(user, "tribe", node, parent_id, parent_name)
        created += n
        if resolved is not None:
            changed.add("tribe_path")
        # an auto-resolved node now carries its canonical id, so the next
        # level is checked against the right siblings
        parent_id = node.get("id") or ""
        parent_name = node.get("name") or ""

    language = (profile.language or "").strip()
    if language:
        normalized = normalize_name(language)
        known = {normalize_name(l.name): l.name for l in Language.objects.all()}
        if normalized and normalized in known:
            if profile.language != known[normalized]:
                profile.language = known[normalized]
                changed.add("language")
        elif normalized:
            n, _ = _add_suggestion(
                user, "language", {"name": language, "pending": True}, "", "",
            )
            created += n

    if changed:
        profile.save(update_fields=[*changed, "updated_at"])
    return created


def _repoint(kind, suggestion, ref_id, ref_name):
    """Rewrite every profile still holding the pending entry."""
    normalized = suggestion.normalized_name
    updated = 0
    for profile in Profile.objects.exclude(completed_at=None):
        changed = False
        if kind == "tribe":
            for node in profile.tribe_path or []:
                if (
                    isinstance(node, dict)
                    and node.get("pending")
                    and normalize_name(node.get("name") or "") == normalized
                ):
                    node["id"] = ref_id
                    node["name"] = ref_name
                    node.pop("pending", None)
                    changed = True
        elif kind == "language":
            if normalize_name(profile.language or "") == normalized:
                profile.language = ref_name
                changed = True
        else:
            entry = getattr(profile, kind)
            if (
                isinstance(entry, dict)
                and entry.get("pending")
                and normalize_name(entry.get("name") or "") == normalized
            ):
                setattr(
                    profile, kind, {"id": ref_id, "name": ref_name},
                )
                changed = True
        if changed:
            field = "tribe_path" if kind == "tribe" else kind
            profile.save(update_fields=[field, "updated_at"])
            updated += 1
    return updated


def _resolve(suggestion, reviewer, status, ref_id):
    suggestion.status = status
    suggestion.resolved_ref_id = ref_id
    suggestion.reviewed_by = reviewer
    suggestion.reviewed_at = timezone.now()
    suggestion.save()


def approve_suggestion(suggestion: Suggestion, reviewer) -> str:
    kind = suggestion.kind
    name = suggestion.name
    if kind == "tribe":
        parent = Tribe.objects.filter(id=suggestion.parent_id).first()
        level = parent.level + 1 if parent else 1
        base = (
            f"{parent.id}--{slug_part(name)}" if parent else f"tribe-{slug_part(name)}"
        )
        row = Tribe.objects.create(
            id=unique_ref_id(Tribe, base),
            name=name,
            parent=parent,
            level=level,
            level_name=LEVEL_NAMES[min(level, len(LEVEL_NAMES) - 1)],
            country=parent.country if parent else "PK-KP",
        )
    elif kind == "district":
        parent = Province.objects.filter(id=suggestion.parent_id).first()
        if parent is None:
            raise ValueError("district suggestion has no known province")
        row = District.objects.create(
            id=unique_ref_id(District, f"{parent.id}-{slug_part(name)}"),
            name=name,
            province=parent,
        )
    elif kind == "tehsil":
        parent = District.objects.filter(id=suggestion.parent_id).first()
        if parent is None:
            raise ValueError("tehsil suggestion has no known district")
        row = Tehsil.objects.create(
            id=unique_ref_id(Tehsil, f"{parent.id}-{slug_part(name)}"),
            name=name,
            district=parent,
        )
    elif kind == "province":
        from apps.ref.models import Country

        parent = Country.objects.filter(id=suggestion.parent_id).first()
        if parent is None:
            raise ValueError("province suggestion has no known country")
        row = Province.objects.create(
            id=unique_ref_id(Province, f"{parent.id}-{slug_part(name)}"),
            name=name,
            country=parent,
        )
    elif kind == "language":
        row = Language.objects.create(
            id=unique_ref_id(Language, f"lang-{slug_part(name)}"),
            name=name,
        )
    else:
        raise ValueError(f"unknown suggestion kind {kind}")

    _repoint(kind, suggestion, row.id, row.name)
    _resolve(suggestion, reviewer, "approved", row.id)
    return row.id


def merge_suggestion(suggestion: Suggestion, reviewer) -> str:
    if suggestion.kind != "tribe":
        raise ValueError("merge is only supported for tribe suggestions")
    target = suggestion.merge_into
    if target is None:
        raise ValueError("set 'merge into' on the suggestion first")
    known = {normalize_name(target.name)} | {
        normalize_name(a) for a in (target.aliases or [])
    }
    if suggestion.normalized_name not in known:
        target.aliases = [*(target.aliases or []), suggestion.name]
        target.save(update_fields=["aliases"])
    _repoint("tribe", suggestion, target.id, target.name)
    _resolve(suggestion, reviewer, "merged", target.id)
    return target.id


def reject_suggestion(suggestion: Suggestion, reviewer):
    _resolve(suggestion, reviewer, "rejected", "")


def sibling_candidates(suggestion: Suggestion, limit: int = 3):
    """Fuzzy possible-duplicate matches among the suggestion's siblings —
    alias- and suffix-aware, for every suggestion kind."""
    rows = _fuzzy_candidates(
        suggestion.kind,
        suggestion.normalized_name,
        suggestion.parent_id,
        limit=limit,
        cutoff=0.6,
    )
    return [{"id": row.id, "name": row.name} for row in rows]
