"""
Live-wire sensor sanity test.

Prints peak-to-peak ADC readings over USB serial so you can verify the
antenna picks up mains hum before plugging in the OLED. Move the antenna
tip near a known live cable (e.g. a powered lamp's cord) and watch the
numbers jump.

Hardware Setup:
- Antenna wire: GP26 (ADC0)

Run with:
    mpremote run test/live_wire_sensor_test.py
"""

import time
from live_wire_sensor import LiveWireSensor


def main():
    sensor = LiveWireSensor(pin=26)
    print("LiveWireSensor test — sampling GP26 (ADC0).")
    print("Move the antenna near a live cable; numbers should spike.")
    print("Ctrl-C to stop.\n")

    while True:
        p2p = sensor.read()
        bar_len = min(p2p // 200, 60)
        print("p2p={:5d}  {}".format(p2p, "#" * bar_len))
        time.sleep_ms(100)


if __name__ == "__main__":
    main()
