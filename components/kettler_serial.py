#!/usr/bin/env python3

import sys

from serial import Serial, PARITY_NONE
from serial.tools import list_ports

from components.ant import KettlerModel


def get_serial_ports():
    """Returns a list of available serial port names on any platform."""
    return [port.device for port in list_ports.comports()]


def find_kettler_bluetooth(debug):
    """Returns a Kettler instance for the first Kettler Bluetooth serial port found that replies to ID and ST."""

    print("Looking for Kettler Bluetooth device...")

    # Look for ports with KETTLER in the description or hardware ID
    candidates = []
    for port in list_ports.comports():
        port_info = f"{port.device} {port.description} {port.hwid}".upper()
        if "KETTLER" in port_info or "BLUETOOTH" in port_info:
            candidates.append(port.device)

    # If no specific matches, try all available ports
    if not candidates:
        candidates = get_serial_ports()

    print("Found %s candidates" % len(candidates))

    for serial_name in candidates:
        print("Trying: [%s]..." % serial_name)
        try:
            serial_port = Serial(serial_name, timeout=1)
            kettler = Kettler(serial_port, debug)
            kettler_id = kettler.getId()
            if len(kettler_id) > 0:
                print("Connected to Kettler [%s] at [%s]" % (kettler_id, serial_name))
                return kettler
            serial_port.close()
        except Exception as e:
            print(e)

    raise Exception("No Kettler Bluetooth device found")


def find_kettler_usb(debug):
    """Returns a Kettler instance for the first Kettler USB serial port found that replies to ID and ST."""

    print("Looking for Kettler USB device...")

    # Look for USB serial ports
    candidates = []
    for port in list_ports.comports():
        port_info = f"{port.device} {port.description} {port.hwid}".upper()
        # On Windows: look for USB ports (often have "USB" in description)
        # On Linux: /dev/ttyUSB* devices
        # On macOS: /dev/cu.usbserial* or /dev/tty.usbserial*
        if "USB" in port_info or "SERIAL" in port_info:
            candidates.append(port.device)

    # If no USB-specific matches found, try all available ports
    if not candidates:
        candidates = get_serial_ports()

    print("Found %s candidates" % len(candidates))

    for serial_name in candidates:
        print("Trying: [%s]..." % serial_name)
        try:
            serial_port = Serial(serial_name,
                                 baudrate=57600,
                                 parity=PARITY_NONE,
                                 timeout=1)
            kettler = Kettler(serial_port, debug)
            kettler_id = kettler.getId()
            if len(kettler_id) > 0:
                print("Connected to Kettler [%s] at [%s]" % (kettler_id, serial_name))
                return kettler
            serial_port.close()
        except Exception as e:
            print("Failed to connect to [%s]" % serial_name)
            print(e)

    raise Exception("No Kettler USB device found")


def close_safely(thing):
    try:
        thing.close()
    except Exception as e:
        print("Failed to close [%s]: %s" % (str(thing), str(e)))


class Kettler():
    def __init__(self, serial_port, debug=False):
        self.serial_port = serial_port
        self.debug = debug
        self.GET_ID = b"ID\r\n"
        self.GET_STATUS = b"ST\r\n"

    def rpc(self, message):
        self.serial_port.write(message)
        self.serial_port.flush()
        response = self.serial_port.readline().decode('ascii').rstrip()  # rstrip trims trailing whitespace
        return response

    def getId(self):
        return self.rpc(self.GET_ID)

    def readModel(self):
        statusLine = self.rpc(self.GET_STATUS)
        # heartRate cadence speed distanceInFunnyUnits destPower energy timeElapsed realPower
        # 000 052 095 000 030 0001 00:12 030

        segments = statusLine.split()
        if len(segments) == 8:
            heart_rate = int(segments[0])
            cadence = int(segments[1])
            speed = int(segments[2])     # Speed in 0.1 km/h units
            distance = int(segments[3])  # Distance in Kettler units (likely 100m per unit)
            destPower = int(segments[4])
            energy = int(segments[5])    # Energy in kJ
            time_str = segments[6]       # Elapsed time in MM:SS format
            realPower = int(segments[7])

            # Parse elapsed time from MM:SS to seconds
            try:
                parts = time_str.split(':')
                elapsed_time = int(parts[0]) * 60 + int(parts[1])
            except (ValueError, IndexError):
                elapsed_time = 0

            if self.debug and destPower != realPower:
                print("Difference: destPower: %s  realPower: %s" % (destPower, realPower))
            return KettlerModel(realPower, cadence, heart_rate, speed, distance, energy, elapsed_time)
        else:
            print("Received bad status string from Kettler: [%s]" % statusLine)
            return None

    def close(self):
        close_safely(self.serial_port)
