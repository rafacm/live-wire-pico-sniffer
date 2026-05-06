# How the Live-Wire Sniffer Detects Wires

This page explains, end to end, how the device decides that the antenna is near a live conductor — both the underlying physics and what the on-screen elements are showing. For the per-constant tuning reference, see [features/live-wire-detection.md](features/live-wire-detection.md).

## Why an antenna instead of a sensor IC

A mains conductor radiates an electric field at 50/60 Hz whether or not current is flowing through it. An insulated jumper near it picks up a small AC voltage by **capacitive coupling** through the air gap and the insulation — the same physics as a commercial non-contact voltage pen. We sample that voltage with the Pico's ADC.

A coil/solenoid antenna would instead pick up the *magnetic* field, which exists only while current is flowing. That misses live-but-unloaded wires (the ones you most don't want to drill into), so we use a straight-wire electric-field antenna.

## Signal pipeline

```
   mains conductor (50/60 Hz E-field)
           │
           │  capacitive coupling (air + insulation)
           ▼
   antenna jumper ──► ADC0 (GP26) ──► peak-to-peak over 40 ms (≈ 2 cycles @ 50 Hz)
                                              │
                                              ▼
                                    raw current (0…65535 counts)
                                              │
                            ┌─────────────────┴─────────────────┐
                            ▼                                   ▼
                   baseline (slow EMA,                    max_excursion
                   only updates when calm)                (peak envelope, decays)
                            ▼                                   ▼
                            └─────────── excursion ─────────────┘
                                = current - baseline (clamped ≥ 0)
                                              │
                            ┌─────────────────┼─────────────────┐
                            ▼                 ▼                 ▼
                       History strip      Bar fill          DETECTED
                       (autoscaled)      (autoscaled)      (3 guards)
```

## What you see on the OLED

```
┌────────────────────────────────────────────────────────────────┐
│ Live Wire                                          1500        │ ← header: label + excursion
│ ───────────────────────────────────────────────────────────────│
│                                  ▄▄                            │
│                                 ▄██▄        ▄▄                 │
│                              ▄ ▄████▄  ▄▄  ████                │ ← history strip
│ ▄▄ ▄▄▄ ▄▄  ▄▄ ▄▄▄ ▄▄ ▄  ▄ ▄▄▄█▄██████▄████▄████▄▄▄ ▄  ▄▄ ▄ ▄   │  (oldest left, newest right)
│ ───────────────────────────────────────────────────────────────│
│                                                                │
│  ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │ ← magnitude bar
│  ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │   (filled by excursion,
│  ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │    autoscaled to max excursion)
│ ───────────────────────────────────────────────────────────────│
│ LOW                MED                                   MAX   │ ← tick labels
│                                                                │
│                       ▓▓▓ DETECTED ▓▓▓                         │ ← status slot (see below)
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

| Region          | What it shows                                                | Driven by                         |
|-----------------|--------------------------------------------------------------|-----------------------------------|
| Header value    | Counts above the local noise floor                            | `_excursion`                      |
| History strip   | Last 128 ticks, scrolling right→left                         | `_excursion / _max_excursion`     |
| Magnitude bar   | Current sample, three-quarters above means "loud"            | `_excursion / _max_excursion`     |
| Status slot     | During warm-up: alternates `WARMING UP` / `WAIT` every 500 ms so the user sees the device is booting. After warm-up: lights `DETECTED` only when all detection guards pass. | `_sample_count`, then *Detection rule* |

## Baseline, excursion, max excursion

The display autoscale and the detection logic are **deliberately decoupled** so a raised noise floor cannot by itself trip the detector.

- **`_baseline`** — slow EMA of the raw peak-to-peak reading. Tracks the *local* noise floor (which depends heavily on supply, antenna length, room wiring, and how the user is holding the board). For the first 30 samples (warm-up) it follows a rolling average; afterwards it updates by `baseline += (current - baseline) / 64` only when the reading is "calm". While a real detection is happening the baseline is **frozen** — otherwise a sustained signal would drag the floor up and silently disarm the detector.

- **`_excursion`** = `current - baseline`, clamped to 0. The "useful" signal: how much louder the antenna is right now versus its idle. This is what the bar, history strip, and DETECTED test all read.

- **`_max_excursion`** — running peak of `_excursion`, decayed by × 31/32 every 2 s and floored at 50. Used **only** as the autoscale denominator, not for the detection decision.

## Detection rule

`DETECTED` lights up only when **all three** of these hold simultaneously:

1. `_sample_count > 30` — past the warm-up, so the baseline has settled.
2. `_excursion > _max_excursion / 2` — current sample is at least half of the running peak, i.e. clearly elevated relative to recent activity.
3. `_excursion > 100` — current sample is above an absolute minimum count, so a quiet environment with a tiny `_max_excursion` cannot trip the label.

Walk-through:

- **First ~3 s after boot**: warm-up suppresses `DETECTED` entirely while the baseline settles. The status slot alternates `WARMING UP` and `WAIT` every 500 ms so the user knows readings aren't trustworthy yet. The bar may flicker a little; ignore it.
- **Free air, post warm-up**: excursion sits near 0 (current ≈ baseline). Bar near empty, history strip low and noisy, `DETECTED` off.
- **Sweep toward a live wire**: excursion climbs (e.g. 1 500 counts above a 200-count baseline). `_max_excursion` tracks the rising peak. Once the excursion crosses both the relative half-of-peak threshold and the absolute 100-count floor, the inverted `DETECTED` box appears.
- **Sustained hold near a wire**: the baseline is frozen during detection, so the excursion stays high and `DETECTED` stays on. When you sweep away, excursion drops to ~0; after a brief calm period the baseline can adapt again.

## Calibrating before you trust it

Sensitivity varies wildly with antenna length, supply, and how you hold the board. Always start a session by:

1. Sweeping over a wire you **know** is energized (e.g. a powered lamp's cord). Confirm `DETECTED` lights up and the bar fills.
2. Sweeping over a spot you **know** has no wiring (open floor, middle of a wooden door). Confirm `DETECTED` stays off and the bar stays low.

That gives you a feel for what a real detection looks like on *your* current setup before you point it at anything that matters. The README's main disclaimer applies: this is a hobby project, not a certified NCV tester.

## Tuning

The defaults are chosen for an insulated-jumper antenna 5–10 cm long with the Pico held in hand. If your environment differs and the device is too sensitive (DETECTED in free air) or too insensitive (won't trip near a known live wire), the constants are at the top of [`lib/live_wire_display.py`](../lib/live_wire_display.py). Each one is documented with its reasoning in [features/live-wire-detection.md](features/live-wire-detection.md).
