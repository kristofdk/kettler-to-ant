#!/usr/bin/env python3


class KettlerModel:
    def __init__(self, power=0, cadence=0, heart_rate=0, speed=0, distance=0, energy=0, elapsed_time=0):
        self.power = power
        self.cadence = cadence
        self.heart_rate = heart_rate
        self.speed = speed            # Speed in 0.1 km/h units (as received from Kettler)
        self.distance = distance      # Distance in Kettler units (likely 100m per unit)
        self.energy = energy          # Energy in kJ (as received from Kettler)
        self.elapsed_time = elapsed_time  # Elapsed time in seconds

    def __str__(self):
        return "power[%s] cadence[%s] hr[%s] speed[%s] dist[%s] energy[%s] time[%s]" % (
            self.power, self.cadence, self.heart_rate, self.speed, self.distance,
            self.energy, self.elapsed_time)
