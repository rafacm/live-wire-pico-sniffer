# Live-Wire Pico Sniffer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Let your Raspberry Pi Pico 2 find the live wires before your drill does!**

Non-contact AC voltage detector built on a Raspberry Pi Pico 2, an insulated copper jumper used as an antenna, and a 128×64 SH1106 OLED display. A short jumper wire on an ADC pin capacitively couples to the electric field around mains conductors, and the OLED shows a scrolling history strip plus a magnitude bar that spikes when the probe passes over a live wire.

> ⚠️ **Disclaimer.** This is a hobby project, not a certified non-contact voltage tester. Build, **calibrate** and use at your own risk. The author accepts no liability for damage, injury, or loss caused by use or misuse of this project.

> 🎯 **Calibrate before you trust it.** Sensitivity varies with antenna length, supply, and how you hold the board. Start every session by sweeping over a spot you *know* is energized and one you *know* is clear, so you learn what a real `DETECTED` looks like on your setup. Step-by-step procedure: [Calibrating before you trust it](doc/README.md#calibrating-before-you-trust-it).

## Hardware

![Raspberry Pi Pico 2, an insulated copper jumper used as an antenna, and a 128×64 SH1106 OLED display](doc/images/live-wire-pico-sniffer-foto-1.jpg)

Important points (marked in the image above):
1. Make sure you connect the power supply to the `VSYS` pin and NOT the `VBUS` pin. This way you can power the Pico both from the micro-USB connection and the power supply board.
2. Make sure you select the `5V` pins in the power supply board

See the [Raspberry Pi Pico pinout](https://pico.pinout.xyz/) for pinout details.

For best detection sensitivity, prefer **battery power** (e.g. a single 18650 + holder, or 3×AA, into `VSYS` with USB unplugged). A floating supply gives the cleanest baseline; a mains-derived PSU couples 50/60 Hz hum onto ground and shrinks the contrast between "near a wire" and "free air." See [doc/features/live-wire-detection.md](doc/features/live-wire-detection.md) for details.

The antenna is a single insulated breadboard jumper (solid-core, 22 AWG). One end goes into the ADC pin; the other end is the probe tip. Stripping ~1–2 cm of insulation off the tip slightly increases sensitivity but is optional — the plastic jacket does not block capacitive coupling.

Wire the antenna and OLED to the Pico as follows:

| Signal           | Pin  | Device                       |
|------------------|------|------------------------------|
| ADC0             | GP26 | Antenna jumper (probe wire)  |
| I2C0 SDA         | GP12 | SH1106                       |
| I2C0 SCL         | GP13 | SH1106                       |

Devices: 

| Device | Bus  | I2C Address | Notes |
|--------|------|-------------|-------|
| SH1106 | I2C0 | 0x3C        | 128×64 OLED display |

I2C runs at 400 kHz.

## What the OLED shows

```
┌────────────────────────────────────────────────────────────────┐
│ Live Wire                                          1500        │ ← header: label + excursion
│ ───────────────────────────────────────────────────────────────│
│                                  ▄▄                            │
│                                 ▄██▄        ▄▄                 │
│                              ▄ ▄████▄  ▄▄  ████                │ ← history strip
│ ▄▄ ▄▄▄ ▄▄  ▄▄ ▄▄▄ ▄▄ ▄  ▄ ▄▄▄█▄██████▄████▄████▄▄▄ ▄  ▄▄ ▄ ▄   │   (oldest left,
│ ───────────────────────────────────────────────────────────────│    newest right)
│                                                                │
│  ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │ ← magnitude bar
│  ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │   (filled by excursion,
│  ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   │    autoscaled to max excursion)
│ ───────────────────────────────────────────────────────────────│
│ LOW                MED                                   MAX   │ ← tick labels
│                                                                │
│                       ▓▓▓ DETECTED ▓▓▓                         │ ← status slot
│                                                                │   (alternates "WARMING UP" /
└────────────────────────────────────────────────────────────────┘   "WAIT" during warm-up)
```

For the full annotated walkthrough — what each region is driven by, the baseline/excursion split, the warm-up indicator, and the exact rule that fires `DETECTED` — see [doc/README.md](doc/README.md).

## Project layout

```
main.py                          # Entry point (runs on boot)
AGENTS.md                        # Project instructions (conventions, layout, deploy commands)
CLAUDE.md                        # One-line redirect to AGENTS.md
lib/
  sh1106.py                      # SH1106 OLED driver (I2C, framebuf-based)
  live_wire_sensor.py            # Windowed peak-to-peak ADC sampler
  live_wire_display.py           # OLED rendering: history strip + bar + DETECTED label
test/
  sh1106_test.py                 # On-device display test suite
  live_wire_sensor_test.py       # Prints peak-to-peak readings over serial
  live_wire_display_test.py      # Renders a static demo screen for photographing the OLED
doc/
  README.md                      # How detection works (annotated screen + signal pipeline)
  features/                      # Per-feature documentation (one Markdown file per feature)
  images/                        # Photos and diagrams referenced from this README
```

## Deploying to the board

Use `mpremote` (install with `pip install mpremote`):

### Copy entire project to the board
```bash
mpremote cp -r lib/ test/ *.py :
```

### Copy and run a test file
```bash
mpremote cp test/<test_file>.py :test/ + run test/<test_file>.py
```

### Resetting the board
```bash
mpremote reset
```

## Running tests

Tests run directly on the Pico — there is no host-side test harness. Connect the board via USB and:

```bash
mpremote run test/live_wire_sensor_test.py    # Print peak-to-peak ADC readings
mpremote run test/sh1106_test.py              # OLED display test suite
mpremote run test/live_wire_display_test.py   # Render a static demo screen for photos
```

All test files have a `main()` entry point guarded by `if __name__ == "__main__"`.

`live_wire_display_test.py` does not sample the ADC. It pushes a single representative frame (low-noise baseline plus two simulated wire-pass humps, with the `DETECTED` box visible) and stops, then dims the OLED via `display.contrast(8)` so an iPhone's auto-exposure picks a long enough shutter to avoid the rolling-shutter banding you otherwise get against the panel's internal refresh.

## How the detector works

There is no IC sensor — just an insulated jumper on an ADC pin. A live mains conductor radiates an electric field at 50/60 Hz that capacitively couples into the antenna; the Pico samples the induced peak-to-peak amplitude, subtracts a slow-EMA baseline to get the "excursion above noise", and lights `DETECTED` when the excursion clears both a relative and an absolute threshold past a warm-up gate.

A coil/solenoid antenna would only respond to the magnetic field — present only when current flows — and would miss energized-but-unloaded wires, exactly the case you don't want to drill into.

Full walkthrough with pipeline diagram, baseline/excursion math, three-guard detection rule, and tuning notes: **[doc/README.md](doc/README.md)**. Direct links:

- [Signal pipeline](doc/README.md#signal-pipeline)
- [Baseline, excursion, max excursion](doc/README.md#baseline-excursion-max-excursion)
- [Detection rule](doc/README.md#detection-rule)
- [Tuning](doc/README.md#tuning)

## Acknowledgements

- SH1106 driver and project layout reused from [pico-cardio](https://github.com/rafacm/pico-cardio).
- Built with [Claude](https://claude.ai).

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
