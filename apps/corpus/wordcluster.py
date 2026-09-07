"""Group spellings of the same Pashto word without merging different words.

Two contributors writing الوتونکي and الوتوونکي mean one word spelled two
ways; a Piral Khel الوتونکي and an Ali Khel شېوه are two different words and
must stay apart — that difference IS the dataset. So clustering is
deliberately conservative: same consonant spine AND a close overall spelling.
"""
import difflib

# Letters whose presence, doubling or omission varies between writers:
# long vowels and the hamza carriers. Consonants carry the word's identity.
WEAK_LETTERS = set("اآوؤهةېیۍئي")

SPINE_RATIO = 0.62
NO_SPINE_RATIO = 0.9


def spine(normalized: str) -> str:
    """Consonant skeleton: drop weak letters and collapse repeats."""
    out = []
    for char in normalized:
        if char in WEAK_LETTERS or char.isspace():
            continue
        if out and out[-1] == char:
            continue
        out.append(char)
    return "".join(out)


def _ends_weak(word: str) -> bool:
    return bool(word) and word[-1] in WEAK_LETTERS


def same_word(a: str, b: str) -> bool:
    """Whether two normalized spellings are the same word.

    When in doubt these stay apart: showing two rows a reviewer can merge
    costs nothing, while merging two real words destroys a dialect
    distinction we cannot recover.
    """
    if a == b:
        return True
    # a trailing weak letter on one side only is usually grammar, not
    # spelling — چرګ (rooster) is not چرګه (hen)
    if _ends_weak(a) != _ends_weak(b):
        return False
    spine_a, spine_b = spine(a), spine(b)
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if spine_a and spine_a == spine_b:
        # identical consonant spine — only vowel spelling differs
        return ratio >= SPINE_RATIO
    # no spine to lean on (very short words): demand near-identical spelling
    return ratio >= NO_SPINE_RATIO and abs(len(a) - len(b)) <= 1


def cluster(normalized_forms):
    """Group normalized spellings into words. Returns a list of sets, each
    holding the spellings judged to be one word."""
    groups: list[set[str]] = []
    # longest first so the fuller spelling anchors its group
    for form in sorted(set(normalized_forms), key=lambda f: (-len(f), f)):
        for group in groups:
            if any(same_word(form, member) for member in group):
                group.add(form)
                break
        else:
            groups.append({form})
    return groups
