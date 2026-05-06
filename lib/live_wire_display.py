"""
Live-wire detector display for the SH1106 128x64 OLED.

Layout (Option C — history strip + bar):

    y=0..7    Header: "LIVE WIRE" left, "p2p:NNNN" right
    y=8       horizontal separator
    y=9..30   Scrolling magnitude history (right-to-left, newest on right)
    y=31      horizontal separator
    y=33..41  Horizontal magnitude bar (rect outline + fill)
    y=44..51  Tick labels: "0  LOW  MED  HIGH  MAX"
    y=54..61  "DETECTED" (only when current magnitude exceeds threshold)

Magnitudes are auto-scaled against a slowly-adapting running max so the bar
and history strip remain useful regardless of the absolute signal level
(which depends heavily on supply, antenna length, and how the user holds
the board).
"""

from utime import ticks_ms, ticks_diff

_DISP_W              = 128
_DISP_H              = 64

_HEADER_Y            = 0
_SEP1_Y              = 8
_HIST_TOP            = 9
_HIST_H              = 22                # y=9..30
_SEP2_Y              = 31
_BAR_Y               = 33
_BAR_H               = 9                 # y=33..41
_TICKS_Y             = 44
_DETECTED_Y          = 54

_BAR_X               = 2
_BAR_W               = _DISP_W - 2 * _BAR_X   # 124 px

_DRAW_INTERVAL_MS    = 80                # ~12 Hz refresh
_MAX_DECAY_INTERVAL  = 2000              # ms between max-seen decay steps
_MAX_DECAY_NUMERATOR = 31                # decay factor: max *= 31/32
_MAX_DECAY_DENOM     = 32
_MAX_FLOOR           = 200               # never let auto-scale collapse below this
_DETECT_RATIO_NUM    = 1                 # threshold = max_seen * 1/2
_DETECT_RATIO_DEN    = 2


class LiveWireDisplay:
    """Reads the LiveWireSensor and renders Option C on the SH1106."""

    def __init__(self, sensor, display):
        self._sensor  = sensor
        self._display = display

        self._hist     = bytearray(_DISP_W)   # normalised history, 0.._HIST_H-1
        self._hist_idx = 0                    # next write position (oldest sample)

        self._current   = 0
        self._max_seen  = _MAX_FLOOR

        now = ticks_ms()
        self._last_draw_ms  = now
        self._last_decay_ms = now

    def update(self):
        """Sample once, update history + autoscale, redraw on cadence."""
        p2p = self._sensor.read()
        self._current = p2p

        if p2p > self._max_seen:
            self._max_seen = p2p

        now = ticks_ms()
        if ticks_diff(now, self._last_decay_ms) >= _MAX_DECAY_INTERVAL:
            decayed = (self._max_seen * _MAX_DECAY_NUMERATOR) // _MAX_DECAY_DENOM
            self._max_seen = decayed if decayed >= _MAX_FLOOR else _MAX_FLOOR
            self._last_decay_ms = now

        h = (p2p * (_HIST_H - 1)) // self._max_seen
        if h < 0:
            h = 0
        elif h > _HIST_H - 1:
            h = _HIST_H - 1
        self._hist[self._hist_idx] = h
        self._hist_idx = (self._hist_idx + 1) % _DISP_W

        if ticks_diff(now, self._last_draw_ms) >= _DRAW_INTERVAL_MS:
            self._draw()
            self._last_draw_ms = now

    def _draw(self):
        d = self._display
        d.fill(0)

        # Header — label at left, raw value right-aligned (no "p2p:" prefix
        # so a 5-digit number always fits without overlapping the label).
        d.text("Live Wire", 0, _HEADER_Y)
        val = self._current if self._current < 99999 else 99999
        val_str = "{:5d}".format(val)
        d.text(val_str, _DISP_W - 8 * len(val_str), _HEADER_Y)

        d.hline(0, _SEP1_Y, _DISP_W, 1)

        # History strip — bar columns from bottom of strip upward
        hist    = self._hist
        h_idx   = self._hist_idx
        bot     = _HIST_TOP + _HIST_H - 1
        for x in range(_DISP_W):
            ri = (h_idx + x) % _DISP_W       # oldest → newest left-to-right
            bar_h = hist[ri]
            if bar_h > 0:
                d.vline(x, bot - bar_h, bar_h + 1, 1)

        d.hline(0, _SEP2_Y, _DISP_W, 1)

        # Magnitude bar
        d.rect(_BAR_X, _BAR_Y, _BAR_W, _BAR_H, 1)
        inner_w = _BAR_W - 2
        fill_w = (self._current * inner_w) // self._max_seen
        if fill_w < 0:
            fill_w = 0
        elif fill_w > inner_w:
            fill_w = inner_w
        if fill_w > 0:
            d.fill_rect(_BAR_X + 1, _BAR_Y + 1, fill_w, _BAR_H - 2, 1)

        # Tick labels — LOW left-justified, MED centered, MAX right-justified.
        d.text("LOW", _BAR_X,              _TICKS_Y)
        d.text("MED", (_DISP_W - 24) // 2, _TICKS_Y)
        d.text("MAX", _DISP_W - 24,        _TICKS_Y)

        # DETECTED label — black text on filled white box for emphasis.
        threshold = (self._max_seen * _DETECT_RATIO_NUM) // _DETECT_RATIO_DEN
        if self._current > threshold and self._max_seen > _MAX_FLOOR:
            label = "DETECTED"
            pad   = 2
            box_w = 8 * len(label) + 2 * pad
            box_h = 8 + 2 * pad
            box_x = (_DISP_W - box_w) // 2
            box_y = _DETECTED_Y - pad
            d.fill_rect(box_x, box_y, box_w, box_h, 1)
            d.text(label, box_x + pad, _DETECTED_Y, 0)

        d.show()
