# Errorz Barz

World/pop/hip-hop drum machine patterns, played back as gate/trigger
patterns on [OAM Uncertainty](https://oamodular.org/products/uncertainty),
a 2HP Eurorack module built around an RP2040. 246 patterns transcribed
from Paul Wenzel's *Pocket Operations* booklet, mapped onto Uncertainty's
8 gate outputs and stepped by an external clock. Sibling project to
[68 Certain Teas](https://github.com/themccubbins/68-certain-teas),
same module, same firmware shape, different source material.

## What's here

| File | Purpose |
|---|---|
| `patterns.py` | Raw pattern data (which instrument hits which step, per pattern) |
| `gate_mapping.py` | Dev-time tool: assigns instruments to gate channels, decides play order |
| `realized_patterns.py` | Precomputed step data -- ships to the device |
| `code.py` | Uncertainty firmware -- ships to the device |

`patterns.py` and `gate_mapping.py` are the "build" side and never run
on the module itself; `realized_patterns.py` and `code.py` are the only
two files that need to be copied onto Uncertainty's CIRCUITPY drive.
See the docstrings in each file for the data model, channel-assignment
rules, and why the data is shaped the way it is (there's a real
MemoryError story in there).

## How it works, briefly

The module boots into the first pattern in style order: House, then
other EDM (Electro, Drum and Bass, Miami Bass), then Rock, then all the
Breaks sections together, then regional styles (Afro-Cuban, Reggaeton,
Dub), then everything else. A clock/gate above roughly +4V fires a
short fixed-width trigger on the current step's channels and advances
to the next step. A pulse below roughly -4V advances to the next
pattern, resets to its first step, and -- as long as the input stays
below that threshold -- displays the new pattern's index in binary
across all 8 outputs (channel 1 = least significant bit, channel 8 =
most significant), so the LEDs count up as you cycle through patterns.
Since these are the same 8 gate outputs the drums are patched into, the
binary countup doubles as a bonus rhythmic pattern in its own right.

Channel layout is fixed for every pattern (channel 1 = Bass Drum, 2 =
Snare, 3 = Cymbal, 4 = Closed Hi-Hat, 5 = Open Hi-Hat, 6 = Hand
Clap/Cowbell/Shaker, 7 = Mid Tom/Rimshot/High Tom/Low Tom, 8 = Accent)
-- chosen to balance how often each channel actually does something
across the 246-pattern set, not by drum category. See
`gate_mapping.py`'s docstring for the full reasoning and the (small,
documented) cases where two instruments share a channel.

## License

This project -- `patterns.py`, `gate_mapping.py`, `realized_patterns.py`,
and `code.py` -- is released under the MIT License (see `LICENSE`). The
drum pattern data itself is a transcription of reference material and
isn't original creative work, but the code, data structures, and the
specific arrangement/mapping onto Uncertainty's hardware are.

## Credits & thanks

**Pattern data** is transcribed from Paul Wenzel's [*Pocket
Operations*](https://shittyrecording.studio) (Second Edition, Rev. 3.1,
2024), (c) 2024 Paul Wenzel, some rights reserved. The book itself
states: "Material in this booklet is intended for educational use. It
is the reader's responsibility to ensure their derived works comply
with copyright laws in their jurisdiction." All credit for the actual
musical content belongs there -- go buy the book, or grab the free PDF
and send a few dollars to [Tree Trust](https://treetrust.org/non-profit/donate/)
(the tree-planting nonprofit the author asks readers to support instead
of a price tag on the PDF).

**The idea** is the second project built on the same firmware shape as
[68 Certain Teas](https://github.com/themccubbins/68-certain-teas),
which started from poking around [Seaside Modular's
Tala](https://github.com/abluenautilus/SeasideModularVCV) module for
VCV Rack. See that project's README for the fuller lineage.

**The hardware/platform** is [OAM Uncertainty](https://oamodular.org/products/uncertainty)
by Olivia Artz Modular, an open-source gate-processor/scripting platform
for Eurorack. Uncertainty's hardware and official firmware are licensed
CC BY-SA 4.0; its logo and branding are copyrighted separately and
reserved (not used here). This project targets Uncertainty's documented
pinout and I/O behavior but is original code written for it, not a
derivative of OAM's own firmware.

**Built by** Claude (Sonnet), an AI model by Anthropic, working with
cubbs.

## A note on licensing, for what it's worth

I'm not a lawyer, and this isn't legal advice. The source material is
released for educational use with the explicit caveat that it's on the
reader (that's us) to make sure any derived work complies with
copyright law in your jurisdiction -- worth reading that statement
yourself before redistributing this project widely, especially the
pattern data itself. Uncertainty's own firmware is CC BY-SA, a
share-alike license that can carry expectations for derivative works;
this project's code was written from scratch against Uncertainty's
public pinout/I/O documentation rather than by copying or modifying
OAM's firmware, which is the basis for releasing the code separately
under MIT.
