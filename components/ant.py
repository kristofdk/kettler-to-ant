#!/usr/bin/env python3


class PowerModel:
    def __init__(self, power=0, cadence=0, heart_rate=0):
        self.power = power
        self.cadence = cadence
        self.heart_rate = heart_rate

    def __str__(self):
        return "power[%s] cadence[%s] hr[%s]" % (self.power, self.cadence, self.heart_rate)
