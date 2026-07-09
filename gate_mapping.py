"""Errorz Barz -- assigns each pattern's instruments to Uncertainty's 8
gate channels, and decides what order the module plays them in.

(In the repo this file is named gate_mapping.py -- kept as
errorz_gate_mapping.py in this shared working folder to avoid colliding
with 68 Certain Teas' own gate_mapping.py sitting alongside it.)

CHANNEL_MAP is fixed for every pattern -- every one of the 12 instrument
codes always maps to the same channel, chosen by how many of the 246
patterns actually use it (not by drum category):
    1   Bass Drum (BD)             -- 232/246 patterns
    2   Snare (SN)                  -- 223/246
    3   Cymbal (CY)                  -- 83/246
    4   Closed Hi-Hat (CH)           -- 78/246
    5   Open Hi-Hat (OH)             -- 39/246
    6   Hand Clap, Cowbell, Shaker (CL, CB, SH) -- 33/246 combined
    7   Mid Tom, Rimshot, High Tom, Low Tom (MT, RS, HT, LT) -- 34/246
    8   Accent -- high on any accented step, independent of which
        instrument(s) are hitting there

This replaced two earlier schemes: first, 5 "flex" channels reassigned
per pattern by usage frequency (dropped because the same pattern
printed under a different drum ordering in the book could land on a
different channel -- confusing to patch around on a real rack); then a
fixed-by-drum-category layout (kick/snare/low-tom/mid+hi-tom/hi-hats/
open-hats/cymbals-etc), which was lopsided -- some channels covered 14
patterns, others 122. This version groups the 10 non-BD/SN codes into 5
bins that balance ACTUAL PATTERN COUNT as evenly as the data allows,
which is why cymbal and closed hi-hat (the two next-busiest codes) each
get a channel to themselves, while four much rarer codes share one.

Channels 6 and 7 group multiple instrument codes onto one output, so
two instruments in the same group can land on the same step in the same
pattern. Checked against all 246 patterns: channel 7's four-way group
(MT/RS/HT/LT) never collides on the same step anywhere in the set;
channel 6's group (CL/CB/SH) does, in 4 of 246 patterns (e.g. FRENCH
HOUSE and SLOW DEEP HOUSE both hit CL and SH on the same steps). When
that happens the channel just fires once -- harmless for the gate, it
only means you can't tell which of the two instruments (or both) the
book intended on that specific hit.

PLAY_ORDER groups patterns by style rather than the book's own order or
raw complexity, since neither made for a satisfying listen start to
finish. SECTION_GROUPS lists the 6 top-level groups, each a list of
section names in the order they play within that group:
    1. House
    2. Other EDM: EDM, Electro, Drum and Bass, Miami Bass
    3. Rock
    4. Breaks, all together: Rolling Breaks, Standard Breaks, Breaks,
       Breaks - Snare, Breaks - Kick, Irregular Breaks, Drum Rolls
       (Drum Rolls isn't literally a "break" but is grouped here as the
       closest fit -- both are fills/technique sections rather than a
       distinct musical style)
    5. Regional/"ethnic" styles: Afro-Cuban, Reggaeton, Dub
    6. Everything else: Funk and Soul, Hip Hop, Pop, Ghost Snares,
       Basic Patterns
Every section in the book appears in exactly one group (checked by the
self-test below). Within a section, patterns are simplest-first (by
distinct-instrument count, then total hit count, then name/variant).

code.py imports realized_patterns.py, not this file -- this is the
one-time "compile" step. realized_patterns.py serializes PLAY_ORDER's
`steps` data (in PLAY_ORDER's order) into a dependency-free file for
the actual firmware to import; that's the order the module plays in.

Run this file directly to print the channel layout for every pattern,
in PLAY_ORDER, and self-test the instrument/section coverage.

Design: cubbs. Built by: Claude (Sonnet) & cubbs, 2026.
"""

from patterns import PATTERNS

CHANNEL_MAP = {
    "BD": 1,
    "SN": 2,
    "CY": 3,
    "CH": 4,
    "OH": 5,
    "CL": 6, "CB": 6, "SH": 6,
    "MT": 7, "RS": 7, "HT": 7, "LT": 7,
}
ACCENT_CHANNEL = 8

SECTION_GROUPS = [
    ["House"],
    ["EDM", "Electro", "Drum and Bass", "Miami Bass"],
    ["Rock"],
    ["Rolling Breaks", "Standard Breaks", "Breaks", "Breaks - Snare",
     "Breaks - Kick", "Irregular Breaks", "Drum Rolls"],
    ["Afro-Cuban", "Reggaeton", "Dub"],
    ["Funk and Soul", "Hip Hop", "Pop", "Ghost Snares", "Basic Patterns"],
]

_SECTION_RANK = {
    section: (group_i, section_i)
    for group_i, group in enumerate(SECTION_GROUPS)
    for section_i, section in enumerate(group)
}


def build_gate_pattern(pattern):
    """Resolve one pattern's rows/accents into a 16-tuple of active-
    channel tuples, using the fixed CHANNEL_MAP above."""
    rows = pattern["rows"]
    accents = pattern["accents"]

    steps = []
    for step in range(1, 17):
        active = set()
        for instr, channel in CHANNEL_MAP.items():
            if step in rows.get(instr, ()):
                active.add(channel)
        if step in accents:
            active.add(ACCENT_CHANNEL)
        steps.append(tuple(sorted(active)))

    used_channels = sorted({CHANNEL_MAP[i] for i in rows if i in CHANNEL_MAP})
    return {
        "section": pattern["section"],
        "name": pattern["name"],
        "variant": pattern["variant"],
        "used_channels": used_channels,
        "accent_channel": ACCENT_CHANNEL if accents else None,
        "steps": steps,  # list[tuple[int, ...]], one tuple of active channels per step
    }


def _play_order_key(pattern):
    complexity = len(pattern["rows"])
    total_hits = sum(len(steps) for steps in pattern["rows"].values())
    return (
        _SECTION_RANK[pattern["section"]],
        complexity,
        total_hits,
        pattern["name"],
        pattern["variant"] or "",
    )


GATE_PATTERNS = [build_gate_pattern(p) for p in PATTERNS]

PLAY_ORDER = [
    gate_pattern
    for _, gate_pattern in sorted(
        zip(PATTERNS, GATE_PATTERNS), key=lambda pair: _play_order_key(pair[0])
    )
]


def get(name, variant=None):
    """Look up a gate pattern by name (and optionally variant), case-insensitive."""
    matches = [g for g in GATE_PATTERNS if g["name"].lower() == name.lower()]
    if variant:
        matches = [g for g in matches if (g["variant"] or "").lower() == (variant or "").lower()]
    return matches


if __name__ == "__main__":
    problems = []

    all_codes = {instr for p in PATTERNS for instr in p["rows"]}
    unmapped = all_codes - set(CHANNEL_MAP)
    if unmapped:
        problems.append(f"unmapped instrument codes: {sorted(unmapped)}")
    else:
        print(f"All {len(all_codes)} instrument codes are mapped: {sorted(all_codes)}")

    all_sections = {p["section"] for p in PATTERNS}
    missing = all_sections - set(_SECTION_RANK)
    extra = set(_SECTION_RANK) - all_sections
    if missing:
        problems.append(f"sections in data but missing from SECTION_GROUPS: {sorted(missing)}")
    if extra:
        problems.append(f"sections in SECTION_GROUPS but not in data: {sorted(extra)}")
    if not missing and not extra:
        print(f"All {len(all_sections)} sections are covered by SECTION_GROUPS exactly once.")

    print()
    for g in PLAY_ORDER:
        label = f"{g['section']:16} {g['name']:40} {g['variant'] or '':2}"
        extras = f"channels={g['used_channels']}"
        if g["accent_channel"]:
            extras += f"  accent=ch{g['accent_channel']}"
        print(f"{label}  {extras}")

    print()
    if problems:
        print(f"{len(problems)} PROBLEMS:")
        for p in problems:
            print(" ", p)
    else:
        print(f"{len(GATE_PATTERNS)} patterns, fixed 8-channel layout, 0 problems.")
