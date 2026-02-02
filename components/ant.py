#!/usr/bin/env python3


class PowerModel:
    def __init__(self, power=0, cadence=0, heart_rate=0, speed=0):
        self.power = power
        self.cadence = cadence
        self.heart_rate = heart_rate
        self.speed = speed  # Speed in 0.1 km/h units (as received from Kettler)

    def __str__(self):
        return "power[%s] cadence[%s] hr[%s] speed[%s]" % (self.power, self.cadence, self.heart_rate, self.speed)
