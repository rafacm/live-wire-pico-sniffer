from live_wire_display import LiveWireDisplay
from live_wire_sensor import LiveWireSensor
from machine import I2C, Pin
from sh1106 import SH1106

i2c0 = I2C(0, sda=Pin(12), scl=Pin(13), freq=400_000)  # SH1106

sensor = LiveWireSensor(pin=26)  # GP26 / ADC0
display = SH1106(i2c=i2c0, addr=0x3C)

detector = LiveWireDisplay(sensor, display)

while True:
    detector.update()
