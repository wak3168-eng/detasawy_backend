"""Turn raw contributions into the word table shown against a picture.

Spellings of one word travel together; different dialect words stay apart —
that difference is the dataset. Used both for a single picture and for the
whole collection at once.
"""
from collections import defaultdict

from apps.corpus.wordcluster import cluster


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
    return data
