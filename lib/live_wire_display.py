"""
Live-wire detector display for the SH1106 128x64 OLED.

Layout (Option C — history strip + bar):

    y=0..7    Header: "Live Wire" left, current excursion (right-aligned)
    y=8       horizontal separator
    y=9..30   Scrolling excursion history (right-to-left, newest on right)
    y=31      horizontal separator
    y=33..41  Horizontal magnitude bar (rect outline + fill)
    y=44..51  Tick labels: "LOW   MED   MAX"
    y=54..61  Status slot: alternating "WARMING UP" / "WAIT" while the
              baseline is bootstrapping; "DETECTED" once warm-up has
              passed and the excursion clearly exceeds the noise floor.

Detection vs. display autoscale are deliberately decoupled:

  * `_baseline` is a slow EMA of the raw peak-to-peak reading taken only
    while the signal is calm — it tracks the local noise floor without
    being dragged up by a real detection.
  * `_excursion` is `current - baseline` clamped at zero.
  * `_max_excursion` is the running peak of recent excursions, used purely
    for autoscaling the bar and history strip.
  * DETECTED fires only after warm-up, only when the excursion exceeds
    half of the running peak excursion, and only when that excursion is
    above an absolute minimum count — so free-air noise can never trip
    the label even if the local baseline happens to be high.
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

# Baseline (local noise floor) tracking
_WARMUP_SAMPLES      = 30                # snap baseline to a rolling average for this many samples
_BASELINE_ALPHA_DEN  = 64                # post-warm-up EMA: baseline += (current - baseline) // 64

# Display autoscale (max excursion envelope)
_EXCURSION_DECAY_INTERVAL = 1000         # ms between decay steps
_EXCURSION_DECAY_NUM = 7                 # decay factor: max_excursion *= 7/8 every step
_EXCURSION_DECAY_DEN = 8                 # ⇒ ~7 s time constant
_EXCURSION_FLOOR     = 50                # never let autoscale collapse below this

# DETECTED firing rule
_DETECT_RATIO_NUM    = 1                 # excursion must exceed max_excursion * 1/2
_DETECT_RATIO_DEN    = 2
_DETECT_MIN_EXCURSION = 30               # ...AND exceed this absolute minimum (counts above baseline)

# Warm-up indicator
_WARMUP_BLINK_MS     = 500               # alternate "WARMING UP" / "WAIT" every 500 ms


class LiveWireDisplay:
    """Reads the LiveWireSensor and renders Option C on the SH1106."""

    def __init__(self, sensor, display):
        self._sensor  = sensor
        self._display = display

        self._hist     = bytearray(_DISP_W)   # normalised history, 0.._HIST_H-1
        self._hist_idx = 0                    # next write position (oldest sample)

        self._current        = 0
        self._baseline       = 0
        self._excursion      = 0
        self._max_excursion  = _EXCURSION_FLOOR
        self._sample_count   = 0

        now = ticks_ms()
        self._last_draw_ms  = now
        self._last_decay_ms = now

    def update(self):
        """Sample once, update baseline + history + autoscale, redraw on cadence."""
        p2p = self._sensor.read()
        self._current = p2p
        self._sample_count += 1

        # 1) Decide if this reading is "calm" (i.e. we should let it pull the
        #    baseline). Use the *previous* baseline + max-excursion to avoid
        #    a circular dependency on this tick's own state.
        prev_threshold = (self._max_excursion * _DETECT_RATIO_NUM) // _DETECT_RATIO_DEN
        provisional_excursion = p2p - self._baseline
        if provisional_excursion < 0:
            provisional_excursion = 0
        is_warmup = self._sample_count <= _WARMUP_SAMPLES
        is_calm = (provisional_excursion <= prev_threshold
                   or provisional_excursion < _DETECT_MIN_EXCURSION)

        # 2) Update baseline.
        if is_warmup:
            # Rolling average so the very first samples set a sane floor.
            n = self._sample_count
            self._baseline = (self._baseline * (n - 1) + p2p) // n
        elif is_calm:
            # Slow EMA toward current reading.
            self._baseline += (p2p - self._baseline) // _BASELINE_ALPHA_DEN
        # else: in suspected detection — hold baseline so the signal can't
        # drag it up.

        # 3) Excursion against the (possibly updated) baseline.
        excursion = p2p - self._baseline
        if excursion < 0:
            excursion = 0
        self._excursion = excursion

        # 4) Update peak-excursion envelope (for display autoscale).
        if excursion > self._max_excursion:
            self._max_excursion = excursion

        now = ticks_ms()
        if ticks_diff(now, self._last_decay_ms) >= _EXCURSION_DECAY_INTERVAL:
            decayed = (self._max_excursion * _EXCURSION_DECAY_NUM) // _EXCURSION_DECAY_DEN
            self._max_excursion = decayed if decayed >= _EXCURSION_FLOOR else _EXCURSION_FLOOR
            self._last_decay_ms = now

        # 5) Push into the history ring (normalised against max excursion).
        h = (excursion * (_HIST_H - 1)) // self._max_excursion
        if h < 0:
            h = 0
        elif h > _HIST_H - 1:
            h = _HIST_H - 1
        self._hist[self._hist_idx] = h
        self._hist_idx = (self._hist_idx + 1) % _DISP_W

        # 6) Redraw on cadence.
        if ticks_diff(now, self._last_draw_ms) >= _DRAW_INTERVAL_MS:
            self._draw()
            self._last_draw_ms = now

    def _draw(self):
        d = self._display
        d.fill(0)

        # Header — label at left, excursion (counts above baseline) right-aligned.
        d.text("Live Wire", 0, _HEADER_Y)
        val = self._excursion if self._excursion < 99999 else 99999
        val_str = "{:5d}".format(val)
        d.text(val_str, _DISP_W - 8 * len(val_str), _HEADER_Y)

        d.hline(0, _SEP1_Y, _DISP_W, 1)

        # History strip — bar columns from bottom of strip upward
        hist  = self._hist
        h_idx = self._hist_idx
        bot   = _HIST_TOP + _HIST_H - 1
        for x in range(_DISP_W):
            ri = (h_idx + x) % _DISP_W       # oldest → newest left-to-right
            bar_h = hist[ri]
            if bar_h > 0:
                d.vline(x, bot - bar_h, bar_h + 1, 1)

        d.hline(0, _SEP2_Y, _DISP_W, 1)

        # Magnitude bar (filled by excursion, autoscaled by max excursion).
        d.rect(_BAR_X, _BAR_Y, _BAR_W, _BAR_H, 1)
        inner_w = _BAR_W - 2
        fill_w = (self._excursion * inner_w) // self._max_excursion
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

        # Status slot — black text on a filled white box.
        # During warm-up: alternates "WARMING UP" / "WAIT" so the user can
        # see the device is booting and readings aren't trustworthy yet.
        # After warm-up: shows "DETECTED" only when both remaining guards
        # pass (excursion above relative threshold AND above absolute
        # minimum), so a noisy baseline alone can never trip the label.
        status_label = None
        status_box_w = None
        if self._sample_count <= _WARMUP_SAMPLES:
            status_label = ("WARMING UP"
                            if (ticks_ms() // _WARMUP_BLINK_MS) % 2 == 0
                            else "WAIT")
            # Pin box width to the longer label so it doesn't twitch.
            status_box_w = 8 * len("WARMING UP") + 2 * 2
        else:
            threshold = (self._max_excursion * _DETECT_RATIO_NUM) // _DETECT_RATIO_DEN
            if (self._excursion > threshold
                    and self._excursion > _DETECT_MIN_EXCURSION):
                status_label = "DETECTED"

        if status_label is not None:
            pad = 2
            if status_box_w is None:
                status_box_w = 8 * len(status_label) + 2 * pad
            box_h  = 8 + 2 * pad
            box_x  = (_DISP_W - status_box_w) // 2
            box_y  = _DETECTED_Y - pad
            text_x = box_x + (status_box_w - 8 * len(status_label)) // 2
            d.fill_rect(box_x, box_y, status_box_w, box_h, 1)
            d.text(status_label, text_x, _DETECTED_Y, 0)

        d.show()
