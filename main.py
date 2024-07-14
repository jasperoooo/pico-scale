from machine import Pin, SoftI2C, ADC
import ssd1306
import random
from time import *
from hx711 import HX711
import sys

# OLED init
i2c = SoftI2C(scl=Pin(17), sda=Pin(16))
oled_width = 128
oled_height = 64
oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c)
oled.fill(0)

# VSYS ADC init
adcpin = machine.Pin(29, machine.Pin.IN)
vsys = machine.ADC(29)
conversionFactor = 3 * (3.3/65535)
batteryVoltage = round(vsys.read_u16() * conversionFactor, 1)

# Check if battery is below 3V. It's not really empty but too empty to run the Pico
if batteryVoltage < 3:
    oled.text("BATTERY EMPTY.", 10, 20)
    oled.text("PLEASE RECHARGE.", 0, 36)
    oled.show()
    sys.exit()

# HX711 init
hxClock = 19
hxData = 18
hx = HX711(18, 19, 128) # Data Pin, Clock Pin, Gain

knownWeight = 30 # in g
rawKnownWeight = 20830 # raw value of known weight
scaleFactor = rawKnownWeight / knownWeight

hx.tare()
oled.text("Taring scale...", 0, 0)
oled.show()

hx.set_scale(scaleFactor)
weightTreshold = 0.2 # dead zone for the scale so it's stable at 0g

oled.text("Scale tared!", 0, 16)
oled.show()

#tare button init
last_interrupt_time = 0
debounce_time = 2000 # time before another button press is recognized, in ms
buttonSource= Pin(14, mode=Pin.OUT, value=1) # high GPIO pin next to the button GPIO. Was easier to wire for me, can be any 3.3V source

def tare_button_pressed(pin):
    global last_interrupt_time
    current_time_tare = ticks_ms() # start timer
    
    if current_time_tare - last_interrupt_time > debounce_time: # if timer is longer than 2s
        last_interrupt_time = current_time_tare
        
        oled.fill(0)
        oled.text("Taring scale...", 0, 0)
        oled.show()
        
        hx.tare()
        
        oled.text("Scale tared!", 0, 16)
        oled.show()
        oled.fill(0)
     
tare_button = Pin(15, Pin.IN, Pin.PULL_DOWN)
tare_button.irq(trigger=Pin.IRQ_RISING, handler=tare_button_pressed)

# Flowrate calculation
class Flowrate:
    def __init__(self):
        self.previous_weight = 0.0
        self.previous_time = ticks_ms()

    def calculate_rate(self, current_weight):
        current_time = ticks_ms()
        elapsed_time = ticks_diff(current_time, self.previous_time) / 1000.0  # Convert ms to seconds

        if elapsed_time == 0:
            return 0  # Avoid division by zero

        weight_difference = current_weight - self.previous_weight
        rate = round(weight_difference / elapsed_time, 1)  # grams per second

        # Update previous values
        self.previous_weight = current_weight
        self.previous_time = current_time

        return rate

flowrate = Flowrate()

while True:
    oled.fill(0) # reset OLED to blank
    
    batteryVoltage = round(vsys.read_u16() * conversionFactor, 1) # get battery voltage
    
    weight = hx.get_units(times=6) # get weight, times value is how many values are averaged
    roundedWeight = round(weight, 1)
    
    if -weightTreshold < weight < weightTreshold: # dead zone around 0g
        finalWeight = 0
    else:
        finalWeight = roundedWeight
    
    rate = flowrate.calculate_rate(finalWeight) # get flowrate
    
    # right aligns weight text on the OLED. Depending on digit count, text distance from the left screen edge decreases
    if finalWeight == 0:
        weightSpacing = 68
    elif 0 < abs(finalWeight) < 10:
        weightSpacing = 48
    elif 10 <= abs(finalWeight) < 100:
        weightSpacing = 32
    elif 100 <= abs(finalWeight) < 1000:
        weightSpacing = 16
    elif 1000 <= abs(finalWeight) <= 3000:
        weightSpacing = 0
    elif abs(finalWeight) > 3000:
        weightSpacing = 32
    
    # right alignment for pos or neg values
    if finalWeight >= 0:
        wSpacing = weightSpacing + 16
    elif finalWeight < 0:
        wSpacing = weightSpacing
    
    # right alignment for flow rate, same principle as weight but lower spacings because the text is smaller
    if 0 <= abs(rate) < 10:
        rateSpacing = 70
    elif 10 <= abs(rate) < 100:
        rateSpacing = 62
    elif 100 <= abs(rate) < 1000:
        rateSpacing = 54
    elif 1000 <= abs(rate) <= 3000:
        rateSpacing = 46
    
    if rate >= 0:
        rSpacing = rateSpacing + 8
    elif rate < 0:
        rSpacing = rateSpacing
    
    # error if weight is above 3kg, which is max for my load cell
    if finalWeight > 3000:
        displayWeight = "MAX"
    else:
        displayWeight = str(finalWeight)
        oled.text("g", 102, 30)
        oled.text(str(rate) + "g/s", rSpacing, 48)
    
    oled.text_scaled_16x16(displayWeight, wSpacing, 22) # larger text for weight
    oled.text("max. 3kg", 0, 0)
    
    batteryPercentage = ((batteryVoltage -3)/(4.2 - 3)) * 100 # calculate battery percentage with 4.2V max and 3V min
    displayBattery = str(int(batteryPercentage)) + "%"        
    oled.text(displayBattery, 104, 0)
    
    oled.show()
    sleep(0.1)