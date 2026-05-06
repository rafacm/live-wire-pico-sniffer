"""
Static screen mockup for the live-wire detector.

Renders a single, representative frame to the SH1106 and then stops
updating. Use this when photographing the OLED — without continuous
redraw, the camera captures the full frame instead of catching the
display mid-I2C-flush (which is what produces the partial-image
artifacts).

The frame is built by reaching into LiveWireDisplay's internal state
(history buffer, current value, running max) and calling its draw
routine exactly once. Nothing is sampled from the ADC.

Hardware Setup:
- SDA: GP12
- SCL: GP13
- I2C Address: 0x3C

Run with:
    mpremote run test/live_wire_display_test.py
"""

import urandom
from machine import I2C, Pin
from utime import sleep

from sh1106 import SH1106
from live_wire_display import LiveWireDisplay


class _MockSensor:
    """Stub sensor — read() is never called for the static mockup."""

    def read(self):
        return 0


def _populate_history(detector):
    """Fill the history buffer with low noise plus two humps on the right."""
    hist = detector._hist
    n = len(hist)

    # Background noise: small random heights (0..3 px).
    for x in range(n):
        hist[x] = urandom.getrandbits(2)

    # Two parabolic humps simulating two wires the probe passed over.
    # v = peak * (1 - (d/width)^2), integer math.
    for cx, peak, width in ((78, 18, 14), (108, 13, 10)):
        for x in range(cx - width, cx + width + 1):
            if 0 <= x < n:
                d = x - cx
                v = peak - (d * d * peak) // (width * width)
                if v > hist[x]:
                    hist[x] = v

    # Render left-to-right as oldest → newest.
    detector._hist_idx = 0


def main():
    i2c0 = I2C(0, sda=Pin(12), scl=Pin(13), freq=400_000)
    display = SH1106(i2c=i2c0, addr=0x3C)

    # Dim the OLED hard so the iPhone's auto-exposure picks a long
    # enough shutter (≥ ~1/15 s) to average across multiple panel
    # refresh cycles — kills the rolling-shutter banding that
    # happens at default brightness. Tune up if the photo is too dark.
    display.contrast(8)

    detector = LiveWireDisplay(_MockSensor(), display)

    _populate_history(detector)

    # current / max_seen = 0.75 → bar three-quarters full, above the
    # 0.5 detection threshold, so the DETECTED box is visible.
    detector._current  = 1500
    detector._max_seen = 2000

    detector._draw()

    print("Static frame rendered. Take your picture; ctrl-C to exit.")
    while True:
        sleep(60)


if __name__ == "__main__":
    main()
