"""Fold duplicate tribe rows into one, keeping the richer record.

Pakistani and Afghan sources name the same confederations (Karlani, Sarbani,
Bettani, Ghurghusht) and the same tribes below them, so importing both can
leave two parallel trees. Merging is recursive: matching children fold into
each other rather than piling up beside one another.
"""
from collections import defaultdict

from apps.ref.models import Tribe, TribeDistrict, TribeProvince
from apps.ref.normalize import names_equivalent, normalize_name


def _score(tribe):
    """Richer rows win: more descendants, then Pashto name, then aliases."""
    return (
        tribe.children.count(),
        1 if tribe.pashto else 0,
        len(tribe.aliases or []),
        -len(tribe.id),
    )


def merge_tribe_into(loser: Tribe, keeper: Tribe) -> int:
    """Move everything from `loser` onto `keeper` and delete it. Returns the
    number of rows removed."""
    if loser.pk == keeper.pk:
        return 0

    removed = 0
    keeper_children = list(keeper.children.all())
    for child in list(loser.children.all()):
        twin = next(
            (
                k
                for k in keeper_children
                if names_equivalent(
                    normalize_name(k.name), normalize_name(child.name),
                )
            ),
            None,
        )
        if twin is not None:
            removed += merge_tribe_into(child, twin)
        else:
            child.parent = keeper
            child.level = keeper.level + 1
            child.save(update_fields=["parent", "level"])
            keeper_children.append(child)
            _relevel_children(child)

    if not keeper.pashto and loser.pashto:
        keeper.pashto = loser.pashto
    known = {normalize_name(keeper.name)} | {
        normalize_name(a) for a in (keeper.aliases or [])
    }
    extra = [
        alias
        for alias in [loser.name, *(loser.aliases or [])]
        if normalize_name(alias) not in known
    ]
    if extra:
        keeper.aliases = [*(keeper.aliases or []), *extra]
    keeper.save(update_fields=["pashto", "aliases"])

    for link in loser.district_links.all():
        TribeDistrict.objects.get_or_create(
            tribe=keeper,
            district=link.district,
            defaults={"role": link.role},
        )
    for link in loser.province_links.all():
        TribeProvince.objects.get_or_create(tribe=keeper, province=link.province)

    loser.delete()
    return removed + 1


def _relevel_children(node):
    for child in node.children.all():
        child.level = node.level + 1
        child.save(update_fields=["level"])
        _relevel_children(child)


def dedupe_tribes() -> int:
    """Fold every same-parent, same-name pair in the tree. Returns rows removed."""
    removed = 0
    while True:
        buckets = defaultdict(list)
        for tribe in Tribe.objects.all():
            buckets[(tribe.parent_id, normalize_name(tribe.name))].append(tribe)
        groups = [rows for rows in buckets.values() if len(rows) > 1]
        if not groups:
            return removed
        for rows in groups:
            rows.sort(key=_score, reverse=True)
            keeper = rows[0]
            for loser in rows[1:]:
                removed += merge_tribe_into(loser, keeper)
