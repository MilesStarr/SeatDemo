from utime import ticks_diff
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

class CMD():
    def __init__(self, period: int = 100, washrate: float = 0.001):
        self.cmd = 0.0
        self._rate = 0.0
        self.until = time.ticks_ms()
        self.out = 0.0
        self.period = period
        self._washrate = washrate
    
    def target(self, cmd: float):
        delta = cmd - self.cmd
        self.cmd = cmd
        self._rate = delta / self.period + self._rate*max(0,time.ticks_diff(time.ticks_ms(), self.until))/self.period
        self.until = time.ticks_ms() + self.period

    def rate(self, now):
        if ticks_diff(self.until, now) > 0:
            return self.rate
        return 0

    def washrate(self, now):
        if ticks_diff(now, self.until) > 500:
            # wait half second after reaching target before washing out movement
            return 0
        err_band = 0.0025
        wash_dir = 0
        if self.out < (0.25 * self.cmd - err_band):
            wash_dir = 1
        if self.out > (0.25 * self.cmd + err_band):
            wash_dir = -1
        return self._washrate * wash_dir

class Actuator():
    def __init__(self, channel: int, mean: int = 1_500_000, amp: int = 200_000, ):
        self.channel = PWM(Pin(channel))
        self.mean    = mean
        self.amp     = amp
        self.channel.freq(100)
        self.channel.duty_ns(mean)

    
    def out(self, value: float):
        # value is a proportion of full scale output from -1 to 1
        self.channel.duty_ns(int(self.mean + self.amp * value))
        
