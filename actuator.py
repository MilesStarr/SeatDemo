from machine import UART, Pin, PWM
import time
import math
import rp2

def trapazoidal(timing):
    # 25% neutral dwell, 5% rise time, 15% dwell, 5% to neutral, 25% neutral dwell, 5% fall time, 15% dwell, 5% to neutral
    if 0 >= timing >= 1:    # timing should be a 0 to 1 bounded float
        return 0        
    if timing < 0.25:
        return 0
    timing -= 0.25
    if timing < 0.05:
        return timing/0.05
    timing -= 0.05
    if timing < 0.15:
        return 1
    timing  -= 0.15
    if timing < 0.05:
        return 1 - (timing / 0.05)
    timing -= 0.05
    if timing < 0.25:
        return 0
    timing -= 0.25
    if timing < 0.05:
        return -1 * timing / 0.05
    timing -= 0.05
    if timing < 0.15:
        return -1
    timing -= 0.15        
    return timing/0.05 - 1


class Actuator():
    def __init__(self, channel: int, mean = 1_500_000, amp = 200_000, ):
        self.channel = PWM(Pin(channel))
        self.mean    = mean
        self.amp     = amp
        self.channel.freq(100)
        self.channel.duty_ns(mean)

    
    def out(self, value: float):
        # value is a proportion of full scale output from -1 to 1
        self.channel.duty_ns(int(self.mean + self.amp * value))
        
