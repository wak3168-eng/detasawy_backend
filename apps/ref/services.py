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
from apps.ref.normalize import normalize_name, slug_part, unique_ref_id

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


def _add_suggestion(user, kind, entry, parent_id, parent_name):
    entry = _entry(entry)
    name = (entry.get("name") or "").strip()
    if not entry.get("pending") or not name:
        return 0
    normalized = normalize_name(name)
    if not normalized:
        return 0
    _, created = Suggestion.objects.get_or_create(
        kind=kind,
        normalized_name=normalized,
        parent_id=parent_id or "",
        defaults={
            "name": name,
            "parent_name": parent_name or "",
            "suggested_by": user,
        },
    )
    if not created:
        Suggestion.objects.filter(
            kind=kind,
            normalized_name=normalized,
            parent_id=parent_id or "",
            status="pending",
        ).exclude(suggested_by=user).update(
            times_suggested=F("times_suggested") + 1,
        )
    return 1 if created else 0


def capture_suggestions(profile: Profile) -> int:
    """Extract every pending entry in a profile into the review queue."""
    user = profile.user
    country = _entry(profile.country)
    province = _entry(profile.province)
    district = _entry(profile.district)
    created = 0
    created += _add_suggestion(
        user, "province", profile.province, country.get("id"), country.get("name"),
    )
    created += _add_suggestion(
        user, "district", profile.district, province.get("id"), province.get("name"),
    )
    created += _add_suggestion(
        user, "tehsil", profile.tehsil, district.get("id"), district.get("name"),
    )
    parent_id = ""
    parent_name = ""
    for node in profile.tribe_path or []:
        node = _entry(node)
        created += _add_suggestion(user, "tribe", node, parent_id, parent_name)
        parent_id = node.get("id") or ""
        parent_name = node.get("name") or ""

    language = (profile.language or "").strip()
    if language:
        normalized = normalize_name(language)
        known = {normalize_name(l.name) for l in Language.objects.all()}
        if normalized and normalized not in known:
            created += _add_suggestion(
                user, "language", {"name": language, "pending": True}, "", "",
            )
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
