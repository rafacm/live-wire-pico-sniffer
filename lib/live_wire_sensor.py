"""
Live-wire sensor for the Raspberry Pi Pico 2.

Samples a single ADC pin connected to a short antenna wire, computing the
peak-to-peak amplitude over a fixed-duration window. The window length is
chosen to span ~2 cycles of mains AC (50/60 Hz), so a wire near a live
conductor produces a much larger peak-to-peak reading than free air.

No external components — just an insulated jumper soldered/clipped to the
ADC pin acting as an antenna.
"""

from machine import ADC, Pin
from utime import ticks_us, ticks_diff, ticks_add


class LiveWireSensor:
    """Windowed peak-to-peak reader on a single ADC pin."""

    def __init__(self, pin=26, sample_rate_hz=4000, window_ms=40):
        self._adc = ADC(Pin(pin))
        self._n = max(1, (sample_rate_hz * window_ms) // 1000)
        self._interval_us = 1_000_000 // sample_rate_hz

    def read(self):
        """Return peak-to-peak ADC value (0..65535) over one window."""
        adc = self._adc
        n = self._n
        interval_us = self._interval_us

        mn = 65535
        mx = 0
        next_t = ticks_us()
        for _ in range(n):
            while ticks_diff(ticks_us(), next_t) < 0:
                pass
            v = adc.read_u16()
            if v < mn:
                mn = v
            if v > mx:
                mx = v
            next_t = ticks_add(next_t, interval_us)
        return mx - mn
