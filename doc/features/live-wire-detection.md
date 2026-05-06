# Live-wire detection

## Problem

Detect AC mains conductors hidden in a wall using only the parts already on hand: a Raspberry Pi Pico 2, a 128×64 SH1106 OLED, and a single insulated jumper wire as the probe. No dedicated NCV chip, no op-amp front-end, no JFET buffer — the simplest possible build.

## Approach

Capacitive coupling. A short antenna wire near an energized conductor picks up a small AC voltage at mains frequency (50/60 Hz). With the antenna connected to a Pico ADC pin, the induced signal can be sampled directly and its peak-to-peak amplitude reported as a "spike magnitude."

Magnetic-field (inductive coil) pickup was rejected: it only responds when the wire is carrying current, missing energized-but-unloaded wires — exactly the case the user cares about for "don't drill here."

## Signal path

```
mains conductor ─ E-field ─▶ antenna jumper ─▶ ADC0 (GP26)
                                                    │
                                       windowed peak-to-peak (40 ms)
                                                    │
                                ┌───────────────────┴────────────────────┐
                                ▼                                        ▼
                  scrolling history strip                       horizontal magnitude bar
                                                                         │
                                                                         ▼
                                                       "DETECTED" if current > max_seen / 2
```

## Key parameters

| Parameter | Value | Where | Why |
|---|---|---|---|
| ADC pin | GP26 (ADC0) | `main.py` | Default ADC channel; physical position is convenient on the Pico header. |
| Sample rate | 4 kHz | `live_wire_sensor.py` `sample_rate_hz` | Generous oversampling of 50/60 Hz; fits comfortably in pure-Python sampling loop. |
| Window length | 40 ms | `live_wire_sensor.py` `window_ms` | Captures 2 full cycles at 50 Hz, ≈ 2.4 at 60 Hz — enough to reliably observe peak and trough. |
| Display refresh | ~12 Hz | `live_wire_display.py` `_DRAW_INTERVAL_MS = 80` | Fast enough to feel responsive while sweeping; slow enough that SH1106 I2C doesn't bottleneck the loop. |
| Auto-scale floor | 200 | `_MAX_FLOOR` | Prevents the running-max auto-scale from collapsing toward zero during long stretches in free air, which would cause noise to look like a detection. |
| Auto-scale decay | × 31/32 every 2 s | `_MAX_DECAY_*` | Lets the bar adapt back down after a strong reading so subsequent passes register clearly. |
| Detection threshold | current > max_seen / 2 | `_DETECT_RATIO_*` | Relative threshold avoids needing per-environment calibration; the ratio is forgiving enough that the label stays on through a full sweep over a wire. |

## Powering the Pico

Powering choice noticeably affects sensitivity, because the antenna's induced voltage is measured *relative to the Pico's ground*.

| Supply | Effect on baseline | Notes |
|---|---|---|
| Battery on `VSYS` (e.g. 18650, 3×AA), USB unplugged | **Quietest** — supply fully floats; ground reference comes from user's body | Recommended for handheld use. |
| Breadboard PSU (MB102) on `VSYS` | Noisier baseline; PSU's wall-wart leaks mains hum onto ground | Same scheme as pico-cardio; fine for development on the bench. |
| USB from a laptop/desktop | Similar to MB102, slightly cleaner with battery-powered laptop | Convenient for `mpremote` iteration. |

## Verification

```bash
mpremote cp -r lib/ test/ *.py :
mpremote run test/live_wire_sensor_test.py
```

Expected behaviour:

1. In free air, peak-to-peak readings are small and roughly stable (a few hundred counts of ADC noise).
2. Bringing the antenna near a powered cable (e.g. a lit lamp's cord) makes the printed numbers jump by an order of magnitude.
3. Touching the antenna tip directly to a metal lamp body or unshielded conductor produces a very large reading.
4. Holding the Pico in your hand consistently raises sensitivity over leaving it on a desk untouched.

Then deploy `main.py`:

```bash
mpremote reset
```

Expected on-device behaviour: scrolling history strip stays low and noisy in free air; sweeping the antenna toward a live wire raises the magnitude bar and grows a hump on the strip; once it crosses the threshold the `DETECTED` label appears.

## Files modified

- `main.py` — wire SH1106 (I2C0 / GP12-GP13) and `LiveWireSensor` on GP26 into the `LiveWireDisplay` update loop.
- `lib/live_wire_sensor.py` — new module: windowed peak-to-peak ADC sampler.
- `lib/live_wire_display.py` — new module: SH1106 history strip + magnitude bar with auto-scaling and `DETECTED` label.
- `test/live_wire_sensor_test.py` — new test: print peak-to-peak readings with a crude text bar over USB serial.
