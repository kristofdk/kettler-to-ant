#!/usr/bin/env python3

import time

from time import sleep

from components.ant import KettlerModel

from .ant_broadcaster import PowerBroadcaster, HeartRateBroadcaster, SpeedBroadcaster, FitnessEquipmentBroadcaster


def checkRange(min, value, max):
    if value < min:
        return min
    elif value > max:
        return max
    else:
        return value


def currentTimeMillis():
    return int(round(time.time() * 1000))


class PowerWriter:
    def __init__(self, transmitIntervalMillis, networkKey, debug=False):
        self.ant = PowerBroadcaster(networkKey, debug)
        self.hrAnt = HeartRateBroadcaster(networkKey, debug)
        self.speedAnt = SpeedBroadcaster(networkKey, debug)
        self.feAnt = FitnessEquipmentBroadcaster(networkKey, debug)
        self.debug = debug
        self.transmitIntervalSecs = transmitIntervalMillis / 1000.0
        self.kettlerModel = KettlerModel()
        self.running = False
        self.died = False
        self.__markProgress()
        if self.debug:
            print("Set up PowerWriter with transmitIntervalSecs[%s] power[%s] hr[%s] speed[%s] fe[%s]" % (
                self.transmitIntervalSecs, self.ant.deviceId, self.hrAnt.deviceId,
                self.speedAnt.deviceId, self.feAnt.deviceId))

    def __markProgress(self):
        self.lastUpdate = currentTimeMillis()

    def __sendPower(self, power, cadence):
        self.ant.broadcastPower(power, cadence)

    def __sendHeartRate(self, heart_rate):
        self.hrAnt.broadcastHeartRate(heart_rate)

    def __sendSpeed(self, speed, distance):
        self.speedAnt.broadcastSpeed(speed, distance)

    def __sendFitnessEquipment(self, model):
        self.feAnt.broadcast(
            elapsed_time_secs=model.elapsed_time,
            distance_kettler=model.distance,
            speed_tenths_kmh=model.speed,
            heart_rate=model.heart_rate,
            power=model.power,
            cadence=model.cadence,
            energy_kj=model.energy
        )

    def __sendInLoop(self):
        print("Starting Ant+ writing loop...")
        try:
            while self.running:
                self.__sendPower(self.kettlerModel.power, self.kettlerModel.cadence)
                self.__sendHeartRate(self.kettlerModel.heart_rate)
                self.__sendSpeed(self.kettlerModel.speed, self.kettlerModel.distance)
                self.__sendFitnessEquipment(self.kettlerModel)
                self.__markProgress()
                sleep(self.transmitIntervalSecs)
        except Exception as e:
            self.died = True
            print("Failed with exception: %s" % str(e))
        finally:
            if self.debug:
                print("Closing send loop")
            self.ant.close()
            self.hrAnt.close()
            self.speedAnt.close()
            self.feAnt.close()

    def updateModel(self, model):
        self.kettlerModel.power = checkRange(0, model.power, 2048)
        self.kettlerModel.cadence = checkRange(0, model.cadence, 255)
        self.kettlerModel.heart_rate = checkRange(0, model.heart_rate, 255)
        self.kettlerModel.speed = checkRange(0, model.speed, 9999)  # Max ~999.9 km/h
        self.kettlerModel.distance = checkRange(0, model.distance, 65535)  # Kettler distance units
        self.kettlerModel.energy = checkRange(0, model.energy, 65535)  # Energy in kJ
        self.kettlerModel.elapsed_time = checkRange(0, model.elapsed_time, 65535)  # Time in seconds

    def start(self):
        self.running = True
        self.__sendInLoop()

    def awaitRunning(self):
        while not self.running and not self.died:
            sleep(0.1)
        if self.died:
            raise RuntimeError("Runner already died")

    def stop(self):
        self.running = False
