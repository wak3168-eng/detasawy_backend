"""Idempotent enrichment passes run on every seed_ref invocation:
Pashto names for places, and the Afghanistan tribal tree from
data/afghanistan.csv (confederation → branch → tribe → clan → sub-clan,
with per-province presence links)."""
import csv
from pathlib import Path

from apps.ref.models import Province, District, Tribe, TribeProvince
from apps.ref.normalize import names_equivalent, normalize_name, slug_part, unique_ref_id

LEVEL_NAMES = [
    "confederacy",
    "tribe",
    "clan",
    "division",
    "sub_division",
    "section",
    "minor_fraction",
]

PROVINCE_PS = {
    "pk-kp": "خیبر پښتونخوا",
    "pk-punjab": "پنجاب",
    "pk-sindh": "سنده",
    "pk-balochistan": "بلوچستان",
    "pk-gilgit-baltistan": "ګلګت بلتستان",
    "pk-azad-kashmir": "ازاد کشمیر",
    "pk-islamabad-capital-territory": "اسلام اباد",
    "af-badakhshan": "بدخشان",
    "af-badghis": "بادغیس",
    "af-baghlan": "بغلان",
    "af-balkh": "بلخ",
    "af-bamyan": "بامیان",
    "af-daykundi": "دایکندي",
    "af-farah": "فراه",
    "af-faryab": "فاریاب",
    "af-ghazni": "غزني",
    "af-ghor": "غور",
    "af-helmand": "هلمند",
    "af-herat": "هرات",
    "af-jowzjan": "جوزجان",
    "af-kabul": "کابل",
    "af-kandahar": "کندهار",
    "af-kapisa": "کاپیسا",
    "af-khost": "خوست",
    "af-kunar": "کونړ",
    "af-kunduz": "کندز",
    "af-laghman": "لغمان",
    "af-logar": "لوګر",
    "af-maidan-wardak": "میدان وردګ",
    "af-nangarhar": "ننګرهار",
    "af-nimruz": "نیمروز",
    "af-nuristan": "نورستان",
    "af-paktia": "پکتیا",
    "af-paktika": "پکتیکا",
    "af-panjshir": "پنجشیر",
    "af-parwan": "پروان",
    "af-samangan": "سمنګان",
    "af-sar-e-pol": "سرپل",
    "af-takhar": "تخار",
    "af-uruzgan": "اروزګان",
    "af-zabul": "زابل",
    "ov-australia": "استرالیا",
    "ov-bahrain": "بحرین",
    "ov-canada": "کاناډا",
    "ov-germany": "جرمني",
    "ov-kuwait": "کویت",
    "ov-malaysia": "مالیزیا",
    "ov-netherlands": "هالنډ",
    "ov-norway": "ناروې",
    "ov-oman": "عمان",
    "ov-qatar": "قطر",
    "ov-saudi-arabia": "سعودي عربستان",
    "ov-sweden": "سویډن",
    "ov-tu-rkiye": "ترکیه",
    "ov-united-arab-emirates": "متحده عرب امارات",
    "ov-united-kingdom": "برتانیه",
    "ov-united-states": "امریکا",
}

DISTRICT_PS = {
    "pk-kp-abbottabad": "ایبټ اباد",
    "pk-kp-bajaur": "باجوړ",
    "pk-kp-bannu": "بنو",
    "pk-kp-battagram": "بټګرام",
    "pk-kp-buner": "بونېر",
    "pk-kp-charsadda": "چارسده",
    "pk-kp-chitral-lower": "ښکتنی چترال",
    "pk-kp-chitral-upper": "بر چترال",
    "pk-kp-dera-ismail-khan": "ډېره اسماعیل خان",
    "pk-kp-dir-lower": "ښکتنی دیر",
    "pk-kp-dir-upper": "بر دیر",
    "pk-kp-hangu": "هنګو",
    "pk-kp-haripur": "هری پور",
    "pk-kp-karak": "کرک",
    "pk-kp-khyber": "خیبر",
    "pk-kp-kohat": "کوهاټ",
    "pk-kp-kohistan-lower": "ښکتنی کوهستان",
    "pk-kp-kohistan-upper": "بر کوهستان",
    "pk-kp-kolai-palas": "کولۍ پالس",
    "pk-kp-kurram": "کورمه",
    "pk-kp-lakki-marwat": "لکي مروت",
    "pk-kp-malakand": "ملاکنډ",
    "pk-kp-mansehra": "مانسهره",
    "pk-kp-mardan": "مردان",
    "pk-kp-mohmand": "مهمند",
    "pk-kp-north-waziristan": "شمالي وزیرستان",
    "pk-kp-nowshera": "نوښار",
    "pk-kp-orakzai": "اورکزی",
    "pk-kp-peshawar": "پېښور",
    "pk-kp-shangla": "شانګله",
    "pk-kp-south-waziristan": "سوېلي وزیرستان",
    "pk-kp-swabi": "صوابۍ",
    "pk-kp-swat": "سوات",
    "pk-kp-tank": "ټانک",
    "pk-kp-torghar": "تور غر",
}

# CSV province spellings that differ from our seeded rows
PROVINCE_FIXUPS = {"nimroz": "af-nimruz"}


def ensure_pashto_names() -> int:
    changed = 0
    for model, mapping in ((Province, PROVINCE_PS), (District, DISTRICT_PS)):
        for ref_id, ps in mapping.items():
            updated = model.objects.filter(id=ref_id).exclude(pashto=ps).update(
                pashto=ps,
            )
            changed += updated
    return changed


def _relevel(node, level):
    node.level = level
    node.level_name = LEVEL_NAMES[min(level - 1, len(LEVEL_NAMES) - 1)]
    node.save(update_fields=["level", "level_name"])
    for child in node.children.all():
        _relevel(child, level + 1)


def _is_ancestor_or_self(candidate, node):
    while node is not None:
        if node.pk == candidate.pk:
            return True
        node = node.parent
    return False


def _ensure_child(parent, name):
    """Find-or-create an AF tribe node named `name` under `parent` (None for
    roots). Reuses an equivalent existing child; adopts an equivalent old
    flat root (re-parenting its subtree) before creating anything new."""
    normalized = normalize_name(name)
    if parent is not None and names_equivalent(normalize_name(parent.name), normalized):
        return parent
    siblings = (
        Tribe.objects.filter(parent=parent)
        if parent is not None
        else Tribe.objects.filter(parent__isnull=True, country="AF")
    )
    for row in siblings:
        candidates = [row.name, *(row.aliases or [])]
        if any(names_equivalent(normalize_name(c), normalized) for c in candidates):
            return row

    if parent is None:
        # a confederation may already live nested in the older data
        # (e.g. Durrani under Sarbani) — graft onto it rather than duplicate
        for row in Tribe.objects.filter(country="AF", level__lte=2):
            if names_equivalent(normalize_name(row.name), normalized):
                return row

    if parent is not None:
        flat = Tribe.objects.filter(parent__isnull=True, country="AF", level=1)
        for row in flat:
            if _is_ancestor_or_self(row, parent):
                continue
            if names_equivalent(normalize_name(row.name), normalized):
                row.parent = parent
                row.save(update_fields=["parent"])
                _relevel(row, parent.level + 1)
                return row

    level = parent.level + 1 if parent is not None else 1
    base = f"{parent.id}--{slug_part(name)}" if parent is not None else f"af-{slug_part(name)}"
    return Tribe.objects.create(
        id=unique_ref_id(Tribe, base),
        name=name,
        parent=parent,
        level=level,
        level_name=LEVEL_NAMES[min(level - 1, len(LEVEL_NAMES) - 1)],
        country="AF",
    )


def ensure_afghanistan_tribes(data_dir: Path) -> tuple[int, int]:
    path = data_dir / "afghanistan.csv"
    if not path.exists():
        return 0, 0

    provinces = {normalize_name(p.name): p for p in Province.objects.filter(id__startswith="af-")}
    for wrong, ref_id in PROVINCE_FIXUPS.items():
        row = Province.objects.filter(id=ref_id).first()
        if row:
            provinces[wrong] = row

    before = Tribe.objects.filter(country="AF").count()
    links = 0
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            conf = (row.get("confederation") or "").strip()
            ethnic = (row.get("ethnic_group") or "").strip()
            tribe = (row.get("tribe") or "").strip()
            if not tribe:
                continue

            if conf:
                base = conf.split("(")[0].strip()
                branch = conf.split("(")[1].rstrip(")").strip() if "(" in conf else ""
                node = _ensure_child(None, base)
                if branch:
                    node = _ensure_child(node, branch)
            else:
                node = _ensure_child(None, ethnic or "Other")

            tribe_node = _ensure_child(node, tribe)
            clan = (row.get("clan") or "").strip()
            sub = (row.get("sub_clan") or "").strip()
            deeper = tribe_node
            if clan:
                deeper = _ensure_child(deeper, clan)
            if sub:
                deeper = _ensure_child(deeper, sub)

            province = provinces.get(normalize_name(row.get("province") or ""))
            if province is not None:
                _, created = TribeProvince.objects.get_or_create(
                    tribe=tribe_node, province=province,
                )
                links += 1 if created else 0

    return Tribe.objects.filter(country="AF").count() - before, links
