# Live-Wire Pico Sniffer

MicroPython non-contact AC voltage detector running on a **Raspberry Pi Pico 2**. An insulated jumper wire on ADC0 acts as an antenna; peak-to-peak amplitude over a 40 ms window is rendered on a 128×64 SH1106 OLED as a scrolling history strip plus a magnitude bar.

## Hardware

| Signal   | Pin  | Device                      |
|----------|------|-----------------------------|
| ADC0     | GP26 | Antenna jumper (probe wire) |
| I2C0 SDA | GP12 | SH1106 OLED                 |
| I2C0 SCL | GP13 | SH1106 OLED                 |

I2C runs at 400 kHz. The OLED is at address `0x3C`.

The Pico is powered via `VSYS` (not `VBUS`) so it can run from either USB or an external 5 V supply. Battery power on `VSYS` (with USB unplugged) gives the cleanest baseline for detection — see `doc/features/live-wire-detection.md`.

## Project layout

- `main.py` — entry point that runs on boot.
- `lib/` — driver and rendering modules. Anything here is automatically importable by MicroPython.
- `test/` — on-device test scripts. Each has a `main()` entry point guarded by `if __name__ == "__main__"`.
- `doc/features/` — one Markdown file per feature or significant change.
- `doc/images/` — photos and diagrams referenced from the README.

See `README.md` for the current contents of each directory and what each test does.

**When you add, remove, or rename a module or test file, update the project-layout block and the "Running tests" section in `README.md` so the human-facing inventory stays accurate.** Nothing in `AGENTS.md` should need to change for those edits — the file describes the directory roles, not their contents.

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

Tests run directly on the Pico — there is no host-side test harness. Connect the board via USB and run:

```bash
mpremote run test/<test_file>.py
```

Each test has a `main()` entry point guarded by `if __name__ == "__main__"`.

## Conventions

- **MicroPython built-ins only** — no pip packages, no external dependencies. Use `machine`, `framebuf`, `utime`, `array`, etc.
- Drivers and rendering modules live under `lib/` so MicroPython's import path finds them automatically.
- Code must fit in the Pico's constrained RAM — keep allocations small, prefer pre-allocated buffers (e.g. `bytearray`, `array.array`) over per-frame list construction.
- **Sensor and display are decoupled**: sensor classes return raw integer readings; display/rendering classes own all auto-scaling, smoothing, and thresholding. This lets test scripts exercise sensors without pulling in the OLED, and lets the display be replaced without touching sampling logic.

## Documentation

Feature documentation lives in `doc/features/`, one Markdown file per feature or significant change. Each document should include:

- **Problem** — what was wrong or what need the feature addresses.
- **Changes** — what was modified, with enough detail that a reader can understand the approach without reading the diff.
- **Key parameters** — any tunable constants, their values, and why those values were chosen.
- **Verification** — how to test the change on-device (deploy command + expected behaviour).
- **Files modified** — list of touched files with a one-line summary of each change.

Keep prose concise. Prefer tables and lists over long paragraphs. Use code blocks for CLI commands and signal-flow diagrams. Add an entry for each feature or fix in the `Features & Fixes` section of `README.md`.
