"""Turn raw contributions into the word table shown against a picture.

Spellings of one word travel together; different dialect words stay apart —
that difference is the dataset. Used both for a single picture and for the
whole collection at once.
"""
from collections import defaultdict
from math import sqrt

from apps.corpus.wordcluster import cluster


PLACE_DIMENSIONS = {"country", "province", "district", "tehsil"}
TRIBE_LEVELS = {"tribe": 0, "clan": 1, "subclan": 2}


def _value(row, field):
    return row.get(field) if isinstance(row, dict) else getattr(row, field, None)


def dimension_value(row, dimension):
    """Return the stable key and display name for one snapshotted dimension."""
    if dimension in PLACE_DIMENSIONS:
        node = _value(row, dimension)
    else:
        path = _value(row, "tribe_path")
        index = TRIBE_LEVELS.get(dimension)
        node = path[index] if isinstance(path, list) and index is not None and len(path) > index else None
    if not isinstance(node, dict):
        return None
    name = node.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    node_id = node.get("id")
    key = node_id.strip() if isinstance(node_id, str) and node_id.strip() else name.strip()
    return {"key": key, "label": name.strip()}


def group_breakdown(rows, dimension):
    """Aggregate the same contribution records into a selectable dimension."""
    groups = {}
    for row in rows:
        value = dimension_value(row, dimension)
        if value is None:
            continue
        entry = groups.setdefault(
            value["key"],
            {"key": value["key"], "label": value["label"], "responses": 0,
             "voices": 0, "promptIds": set()},
        )
        entry["responses"] += 1
        entry["voices"] += bool(_value(row, "audio"))
        prompt_id = _value(row, "prompt_id")
        if prompt_id is not None:
            entry["promptIds"].add(prompt_id)
    result = []
    for entry in groups.values():
        result.append({
            "key": entry["key"], "label": entry["label"],
            "responses": entry["responses"], "voices": entry["voices"],
            "pictures": len(entry["promptIds"]),
        })
    return sorted(result, key=lambda item: (-item["responses"], item["label"].casefold()))


def representative_word(words, minimum_sample=10):
    """Describe the leading response without declaring sparse data correct."""
    total = sum(word["count"] for word in words)
    if not words or not total:
        return None
    top = words[0]
    second = words[1]["count"] if len(words) > 1 else 0
    share = top["count"] / total
    margin = (top["count"] - second) / total
    # 95% Wilson lower bound: conservative confidence in the observed share.
    z = 1.96
    denominator = 1 + z * z / total
    centre = share + z * z / (2 * total)
    spread = z * sqrt((share * (1 - share) + z * z / (4 * total)) / total)
    lower = max(0, (centre - spread) / denominator)
    if total < minimum_sample:
        status = "insufficient"
    elif share >= 0.60 and margin >= 0.15:
        status = "representative"
    else:
        status = "mixed"
    return {
        "word": top["word"], "count": top["count"], "sampleSize": total,
        "share": round(share, 4), "margin": round(margin, 4),
        "confidenceLower": round(lower, 4), "status": status,
    }


def group_words(rows):
    """Rows for ONE prompt -> the words given for it, most said first.

    Each word carries the other spellings people used and a breakdown of who
    said it, by district, tribe and clan. Counts are people; recordings are
    counted separately, since most answers are written only.
    """
    rows = [row for row in rows if row.text_norm]
    if not rows:
        return []

    key_of = {}
    for group in cluster(row.text_norm for row in rows):
        key = min(group)
        for form in group:
            key_of[form] = key

    grouped = defaultdict(
        lambda: {
            "count": 0,
            "display": defaultdict(int),
            "cells": defaultdict(int),
            "cell_voices": defaultdict(int),
        },
    )
    for row in rows:
        entry = grouped[key_of.get(row.text_norm, row.text_norm)]
        entry["count"] += 1
        entry["display"][row.text_raw] += 1
        place = row.district if isinstance(row.district, dict) else {}
        district = place.get("name")
        district = district if isinstance(district, str) and district else "—"
        nodes = row.tribe_path if isinstance(row.tribe_path, list) else []
        path = [
            t["name"] if isinstance(t, dict) and isinstance(t.get("name"), str) else "—"
            for t in nodes
        ]
        tribe = path[0] if path else "—"
        clan = path[1] if len(path) > 1 else ""
        entry["cells"][(district, tribe, clan)] += 1
        if row.audio:
            entry["cell_voices"][(district, tribe, clan)] += 1

    data = []
    for entry in grouped.values():
        spellings = sorted(entry["display"].items(), key=lambda kv: -kv[1])
        data.append(
            {
                "word": spellings[0][0],
                "count": entry["count"],
                "share": 0,
                # every other way people wrote the same word, most used first
                "variants": [{"word": w, "count": n} for w, n in spellings[1:]],
                "voices": sum(entry["cell_voices"].values()),
                "rows": [
                    {
                        "district": d,
                        "tribe": t,
                        "clan": c or None,
                        "count": n,
                        "voices": entry["cell_voices"][(d, t, c)],
                    }
                    for (d, t, c), n in sorted(
                        entry["cells"].items(), key=lambda kv: -kv[1],
                    )
                ],
            },
        )
    data.sort(key=lambda item: -item["count"])
    total = sum(item["count"] for item in data)
    for item in data:
        item["share"] = round(item["count"] / total, 4) if total else 0
    return data
