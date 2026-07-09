"""Errorz Barz -- OAM Uncertainty firmware: steps through 246 world/pop/
hip-hop drum gate patterns from Paul Wenzel's "Pocket Operations".

(In the repo this file is named code.py -- kept as errorz_code.py in
this shared working folder to avoid colliding with 68 Certain Teas' own
code.py sitting alongside it. CircuitPython only auto-runs a file
literally named code.py, so rename it on the way onto CIRCUITPY.)

Setup: copy this file (as code.py) plus realized_patterns.py to the
root of CIRCUITPY.

CHANNEL LAYOUT -- fixed for every pattern (see gate_mapping.py for the
full reasoning behind this specific split):
    1   Bass Drum            5   Open Hi-Hat
    2   Snare                6   Hand Clap, Cowbell, Shaker
    3   Cymbal               7   Mid Tom, Rimshot, High Tom, Low Tom
    4   Closed Hi-Hat        8   Accent

Pattern order is grouped by style -- House, other EDM, Rock, Breaks (all
together), regional styles, then everything else -- baked into
realized_patterns.py's list order at generation time, not sorted here
at boot (see that file's docstring for why: building the sort keys
onboard cost more memory than the firmware could spare).

There's no per-step boolean mask precomputed at startup either, and
realized_patterns.py doesn't store per-step tuples -- it's one flat
`bytes` blob, one byte per step, each byte a channel bitmask (see that
file's docstring for the MemoryError that led here). set_outputs()
below unpacks a step's byte with plain bit tests, which costs a
handful of extra operations per clock pulse -- irrelevant at musical
tempo -- in exchange for the firmware actually fitting in RAM.

CV input (bipolar, ~-5V to +5V) drives clock and pattern-select
separately -- same shape as 68 Certain Teas:

    v > RISING_THRESHOLD_V
        Clock. Advances one step and fires a fixed TRIGGER_LENGTH_S pulse
        on that step's channels, regardless of how long the input stays
        past the threshold -- constant-width triggers regardless of the
        source pulse width.

    v < FALLING_THRESHOLD_V
        Pattern select. Advances to the next pattern (reset to step 0)
        once per crossing, then shows that pattern's index in binary
        across all 8 outputs (channel 1 = bit 0 / LSB, channel 8 = bit 7
        / MSB) for as long as the input stays below the threshold.

    -DEAD_ZONE_V..DEAD_ZONE_V
        Off. Re-arms both triggers.

    Anywhere else: also off, undefined otherwise -- gives hysteresis
    headroom.

Each gate output's LED is hardwired to it on Uncertainty, so there's no
separate LED code needed.

BOOT LOG
    Loading and unpacking 246 patterns' worth of data on an RP2040 with
    limited RAM is the riskiest part of startup, so that section leaves
    a one-line breadcrumb in NVM (a small fixed-size region of flash,
    separate from the CIRCUITPY filesystem) saying how far it got and,
    on failure, which exception and how much free memory was left. It's
    a single _LOG_SIZE-byte record, updated only at a real checkpoint (a
    caught failure or a successful boot) -- deliberately NOT stamped
    with a generic "booting" marker the instant startup begins, because
    that would overwrite the one message you actually want to read
    (last boot's real outcome) before this boot has even proven it'll
    do any better. If this boot fails somewhere we can't even reach a
    checkpoint, the PREVIOUS boot's message just stays there untouched,
    however many times it retries -- no risk of losing it to a fast
    crash loop. Never appended to and never grows, so it can't wear out
    the flash over time, and it doesn't need the storage.remount()
    dance (and the read-only-to-your-computer tradeoff that comes with
    it) that writing to CIRCUITPY itself would.

    A separate, tiny boot-attempt counter (bytes 64-67) IS bumped
    unconditionally at the very start of every boot, before anything
    risky runs -- if the status message looks stale, compare it against
    the counter to tell whether you're in a crash loop that's failing
    before it can even update the message.

    A "boot OK" message only means startup and the CV/pin setup
    finished cleanly -- it does NOT mean the main loop kept running
    afterward. Hardware setup (AnalogIn/DigitalInOut) and the main loop
    itself are both wrapped too, each logging its own FAIL line with
    the pattern/step it was on, so a crash after boot still leaves a
    breadcrumb instead of silently going dark.

    To read it: connect over serial (e.g. Mu's serial console), press
    Ctrl-C to stop the running program and drop to the REPL, then:
        import microcontroller
        bytes(microcontroller.nvm[0:64]).split(b'\\x00')[0]   # last real outcome
        int.from_bytes(microcontroller.nvm[64:68], "little")  # boot attempts

Design: cubbs. Built by: Claude (Sonnet) & cubbs, 2026.
"""

import time
import board
from analogio import AnalogIn
import digitalio
import gc
import microcontroller

_LOG_SIZE = 64        # bytes reserved for the last-real-outcome message
_COUNTER_OFFSET = 64  # 4 bytes: boot-attempt counter, bumped every boot


def _log(status):
    """Best-effort: stamp a short fixed-size status string into NVM,
    only at a real checkpoint -- see BOOT LOG above for why this never
    writes a placeholder just because startup began. Never raises --
    logging should never be the reason the firmware fails to start."""
    try:
        data = status.encode("ascii")[:_LOG_SIZE]
        data += b"\x00" * (_LOG_SIZE - len(data))
        microcontroller.nvm[0:_LOG_SIZE] = data
    except Exception:
        pass


def _bump_boot_counter():
    """Best-effort: increment the 4-byte boot-attempt counter. Safe to
    call unconditionally, first thing, since it doesn't touch anything
    else and can't itself be the cause of a later failure."""
    try:
        n = int.from_bytes(
            bytes(microcontroller.nvm[_COUNTER_OFFSET:_COUNTER_OFFSET + 4]), "little"
        )
        n = (n + 1) % (2 ** 32)
        microcontroller.nvm[_COUNTER_OFFSET:_COUNTER_OFFSET + 4] = n.to_bytes(4, "little")
    except Exception:
        pass


_bump_boot_counter()

try:
    from realized_patterns import STEP_DATA, PATTERN_COUNT, STEPS_PER_PATTERN
except Exception as e:
    _log("FAIL import {} free={}".format(type(e).__name__, gc.mem_free()))
    raise

# ---- CV input calibration ----
# Uncertainty's CV input reads roughly -5V to +5V as a 16-bit unsigned
# value (0-65535), centered at 32768 for 0V -- see OAM's own MicroPython
# examples (software/micropython/clock/boot.py etc), which use exactly
# this `(raw - 32768) / ...` centering.
ADC_CENTER = 32768
ADC_FULLSCALE_VOLTS = 5.0

def raw_to_volts(raw):
    return (raw - ADC_CENTER) / ADC_CENTER * ADC_FULLSCALE_VOLTS

RISING_THRESHOLD_V = 4.0    # "clock advance" trigger -- pulled in from the
FALLING_THRESHOLD_V = -4.0  # +/-5V ceiling/floor for reliable detection
DEAD_ZONE_V = 1.0           # -1V..+1V: re-arm triggers
TRIGGER_LENGTH_S = 0.005    # fixed output pulse width (5ms) -- tune to taste;
                             # most drum/envelope inputs are happy anywhere
                             # from ~1ms to ~10ms

# ---- hardware setup ----
try:
    cv_in = AnalogIn(board.A0)

    GATE_PINS = [board.D1, board.D2, board.D3, board.D6, board.D10, board.D9, board.D8, board.D7]
    outs = [digitalio.DigitalInOut(p) for p in GATE_PINS]
    for out in outs:
        out.direction = digitalio.Direction.OUTPUT
        out.value = False
except Exception as e:
    _log("FAIL hw_setup {} free={}".format(type(e).__name__, gc.mem_free()))
    raise

ALL_OFF = 0  # a step byte with no bits set -- see set_outputs()

_log("boot OK n={} free={}".format(PATTERN_COUNT, gc.mem_free()))


def set_outputs(step_byte):
    """step_byte: one byte, bit (channel - 1) set means that channel
    (1-8) should be on right now. No precomputed mask table and no
    tuple ever built -- see the module docstring for why."""
    for i in range(8):
        outs[i].value = bool((step_byte >> i) & 1)


# ---- state ----
pattern_index = 0
step_index = 0
armed_rising = True
armed_falling = True
pulse_off_at = None  # time.monotonic() deadline for the current CLOCK trigger, or None if idle
pattern_index_mask = ALL_OFF  # binary readout of pattern_index, shown while v < FALLING_THRESHOLD_V

set_outputs(ALL_OFF)  # start silent; first clock pulse lights up step 0

try:
    while True:
        now = time.monotonic()
        volts = raw_to_volts(cv_in.value)

        # end the current CLOCK trigger once its fixed width has elapsed,
        # independent of whatever the input is doing at that moment. (Pattern
        # select, below, isn't timed this way -- it follows the input level.)
        if pulse_off_at is not None and now >= pulse_off_at:
            set_outputs(ALL_OFF)
            pulse_off_at = None

        if volts > RISING_THRESHOLD_V:
            if armed_rising:
                armed_rising = False
                step_index = (step_index + 1) % STEPS_PER_PATTERN
                set_outputs(STEP_DATA[pattern_index * STEPS_PER_PATTERN + step_index])
                pulse_off_at = now + TRIGGER_LENGTH_S
            armed_falling = True

        elif volts < FALLING_THRESHOLD_V:
            if armed_falling:
                armed_falling = False
                pattern_index = (pattern_index + 1) % PATTERN_COUNT
                step_index = 0
                # pattern_index itself, shown in binary, IS already a valid
                # channel bitmask in this scheme (bit 0 = channel 1 = LSB,
                # bit 7 = channel 8 = MSB) as long as it fits in 8 bits --
                # true here since PATTERN_COUNT (246) <= 256.
                pattern_index_mask = pattern_index
            armed_rising = True
            set_outputs(pattern_index_mask)  # held for as long as v stays below threshold

        elif -DEAD_ZONE_V <= volts <= DEAD_ZONE_V:
            set_outputs(ALL_OFF)
            armed_rising = True
            armed_falling = True

        else:
            # between the dead zone and either trigger threshold -- no defined
            # behavior, stay off. Arm state holds steady (wide hysteresis band
            # so a slow-moving or noisy signal can't double-trigger).
            set_outputs(ALL_OFF)
except Exception as e:
    _log(
        "FAIL loop {} p={} s={} free={}".format(
            type(e).__name__, pattern_index, step_index, gc.mem_free()
        )
    )
    raise
