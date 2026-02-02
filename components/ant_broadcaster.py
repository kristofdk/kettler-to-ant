#!/usr/bin/env python3

from ant_support import ant

ANT_NETWORK = 1

ANT_DEVICE_TYPE_POWER = 11
ANT_DEVICE_TYPE_FITNESS_EQUIPMENT = 0x11
ANT_DEVICE_TYPE_HEART_RATE = 120
ANT_DEVICE_TYPE_SPEED = 123

ANT_POWER_CHANNEL_PERIOD = 8182
ANT_HRM_CHANNEL_PERIOD = 8070
ANT_SPEED_CHANNEL_PERIOD = 8118
ANT_FE_CHANNEL_PERIOD = 8192
ANT_FITNESS_EQUIPMENT_TYPE_STATIONARY_BIKE = 21

ANT_POWER_PROFILE_POwER_PAGE = 0x10
ANT_FITNESS_EQUIPMENT_PROFILE_GENERAL_DATA_PAGE = 0x10
ANT_FITNESS_EQUIPMENT_PROFILE_GENERAL_SETTINGS_PAGE = 0x17
ANT_FITNESS_EQUIPMENT_PROFILE_STATIONARY_BIKE_DATA_PAGE = 0x15
ANT_FITNESS_EQUIPMENT_PROFILE_TRAINER_DATA_PAGE = 0x19
ANT_FITNESS_EQUIPMENT_PROFILE_TARGET_POWER_PAGE = 0x31  # head unit -> device


class AntBroadcaster:
    """Base class for ANT+ broadcasters with shared ANT node."""

    _shared_ant = None  # Class-level shared ANT instance

    def __init__(self, network_key, debug, device_type, channel=0, channel_period=ANT_POWER_CHANNEL_PERIOD):
        self.channel = channel
        self.stopped = False

        # Share a single ANT node across all broadcasters
        if AntBroadcaster._shared_ant is None:
            AntBroadcaster._shared_ant = ant.Ant(quiet=not debug, silent=False)
            AntBroadcaster._shared_ant.auto_init()
            AntBroadcaster._shared_ant.set_network_key(network=ANT_NETWORK, key=network_key)

        self._ant = AntBroadcaster._shared_ant

        try:
            self._ant.close_channel(channel)
        except ant.AntWrongResponseException:
            pass

        self._ant.assign_channel(channel=channel,
                                 type=ANT_POWER_PROFILE_POwER_PAGE,
                                 network=ANT_NETWORK)

        self.deviceId = 12329 + device_type
        print("Initialised broadcaster for deviceId[%s] of type[%s] on channel[%s]" % (self.deviceId, device_type, channel))

        self._ant.set_channel_id(channel=channel,
                                 device=self.deviceId,
                                 device_type_id=device_type,
                                 man_id=5)
        self._ant.set_channel_freq(channel, 57)
        self._ant.set_channel_period(channel, channel_period)
        self._ant.set_channel_search_timeout(channel, 40)
        self._ant.open_channel(channel)

    def send_broadcast_data(self, channel, data):
        """Send broadcast data on the specified channel."""
        self._ant.send_broadcast_data(channel, data)

    def close(self):
        """Close this broadcaster's channel."""
        self.stopped = True
        try:
            self._ant.close_channel(self.channel)
        except ant.AntWrongResponseException:
            pass

    def wait_tx(self):
        """Wait for transmission to complete.

        With openant, send_broadcast_data is synchronous so we just need
        a small delay to allow the transmission to complete.
        """
        import time
        time.sleep(0.05)


class PowerBroadcaster(AntBroadcaster):
    def __init__(self, network_key, Debug):
        AntBroadcaster.__init__(self, network_key, Debug, device_type=ANT_DEVICE_TYPE_POWER)
        self.Debug = Debug
        self.power_accum = 0
        self.event_counter = 0
        self.lastPowerUpdate = -1
        self.lastCadenceUpdate = -1

    def broadcastPower(self, power=0, cadence=0):
        self.power_accum += power
        balance = 50

        data = [
            ANT_POWER_PROFILE_POwER_PAGE,
            (self.event_counter + 128) & 0xff,
            0x80 | balance,
            int(cadence),  # 0xff, # instant cadence
            int(self.power_accum) & 0xff,
            (int(self.power_accum) >> 8) & 0xff,
            int(power) & 0xff,
            (int(power) >> 8) & 0xff
        ]

        self.event_counter = (self.event_counter + 1) % 0xff

        if self.Debug or (power != self.lastPowerUpdate) or (cadence != self.lastCadenceUpdate):
            print("Sending data for device[%s]: %40s for power[%s] cadence[%s]" % (
                self.deviceId, str(data), power, cadence))
        self.send_broadcast_data(self.channel, data)
        self.lastPowerUpdate = power
        self.lastCadenceUpdate = cadence
        self.wait_tx()


class FitnessEquipmentBroadcaster(AntBroadcaster):
    """Broadcasts fitness equipment data including energy and elapsed time."""

    # Kettler distance unit in meters
    KETTLER_DISTANCE_UNIT_METERS = 100

    def __init__(self, network_key, debug):
        AntBroadcaster.__init__(self, network_key, debug,
                                device_type=ANT_DEVICE_TYPE_FITNESS_EQUIPMENT,
                                channel=3,
                                channel_period=ANT_FE_CHANNEL_PERIOD)
        self.debug = debug
        self.page_toggle = 0
        self.event_counter = 0
        self.accumulated_power = 0
        self.last_values = {}

    def broadcast(self, elapsed_time_secs=0, distance_kettler=0, speed_tenths_kmh=0,
                  heart_rate=0, power=0, cadence=0, energy_kj=0):
        """
        Broadcast fitness equipment data, alternating between pages.

        Args:
            elapsed_time_secs: Elapsed time in seconds
            distance_kettler: Distance in Kettler units (100m per unit)
            speed_tenths_kmh: Speed in 0.1 km/h units
            heart_rate: Heart rate in BPM
            power: Power in watts
            cadence: Cadence in RPM
            energy_kj: Energy in kJ
        """
        # Alternate between General FE Data (0x10) and Stationary Bike Data (0x15)
        if self.page_toggle % 2 == 0:
            self._broadcastGeneralDataPage(elapsed_time_secs, distance_kettler,
                                           speed_tenths_kmh, heart_rate)
        else:
            self._broadcastStationaryBikePage(cadence, power, energy_kj)

        self.page_toggle += 1

    def _broadcastGeneralDataPage(self, elapsed_time_secs, distance_kettler, speed_tenths_kmh, heart_rate):
        """
        Broadcast General FE Data Page (0x10).

        Format:
        - Byte 0: Data page number (0x10)
        - Byte 1: Equipment type (21 = stationary bike)
        - Byte 2: Elapsed time (0.25s units, rollover at 64s)
        - Byte 3: Distance traveled (meters, rollover at 256m)
        - Bytes 4-5: Speed (0.001 m/s units, uint16_le)
        - Byte 6: Heart rate (0xFF if invalid)
        - Byte 7: Capabilities + FE state
        """
        # Convert distance from Kettler units to meters
        distance_m = distance_kettler * self.KETTLER_DISTANCE_UNIT_METERS

        # Convert speed from 0.1 km/h to 0.001 m/s: (speed/10) * (1000/3600) * 1000
        speed_mms = int(speed_tenths_kmh * 1000 / 36)

        # Capabilities: HR from ANT+, distance enabled, virtual speed
        capabilities = (
            0x2 << 4 |  # HR data source: ANT+ HRM
            0x1 << 2 |  # Distance enabled
            0x0        # Speed is real (not virtual)
        )
        # FE State: In Use (3)
        fe_state = 3 << 4

        data = [
            ANT_FITNESS_EQUIPMENT_PROFILE_GENERAL_DATA_PAGE,  # 0x10
            ANT_FITNESS_EQUIPMENT_TYPE_STATIONARY_BIKE,       # 21
            int(elapsed_time_secs * 4) & 0xFF,                # Time in 0.25s, rollover 64s
            int(distance_m) & 0xFF,                           # Distance in m, rollover 256m
            speed_mms & 0xFF,                                 # Speed LSB
            (speed_mms >> 8) & 0xFF,                          # Speed MSB
            int(heart_rate) if heart_rate > 0 else 0xFF,      # HR or invalid
            capabilities | fe_state                           # Capabilities + state
        ]

        current = ('general', elapsed_time_secs, distance_kettler, speed_tenths_kmh, heart_rate)
        if self.debug or current != self.last_values.get('general'):
            print("FE General: time[%ds] dist[%dm] speed[%.1f km/h] hr[%d]" % (
                elapsed_time_secs, distance_m, speed_tenths_kmh / 10.0, heart_rate))
        self.last_values['general'] = current

        self.send_broadcast_data(self.channel, data)
        self.wait_tx()

    def _broadcastStationaryBikePage(self, cadence, power, energy_kj):
        """
        Broadcast Stationary Bike Specific Data Page (0x15).

        Format:
        - Byte 0: Data page number (0x15)
        - Byte 1: Update event count
        - Byte 2: Instantaneous cadence (RPM)
        - Bytes 3-4: Accumulated power (watts, uint16_le)
        - Bytes 5-6: Instantaneous power (watts, uint16_le, 0.5W resolution on bits 0-11)
        - Byte 7: Flags + FE state
        """
        self.event_counter = (self.event_counter + 1) & 0xFF
        self.accumulated_power = (self.accumulated_power + power) & 0xFFFF

        # Instantaneous power with 1W resolution (bits 0-11), bits 12-15 unused
        instant_power = int(power) & 0x0FFF

        # Flags: power calibration not required
        flags = 0x00
        # FE State: In Use (3)
        fe_state = 3 << 4

        data = [
            ANT_FITNESS_EQUIPMENT_PROFILE_STATIONARY_BIKE_DATA_PAGE,  # 0x15
            self.event_counter,
            int(cadence) & 0xFF,
            self.accumulated_power & 0xFF,
            (self.accumulated_power >> 8) & 0xFF,
            instant_power & 0xFF,
            (instant_power >> 8) & 0x0F,  # Only lower 4 bits used for power
            flags | fe_state
        ]

        # Convert kJ to kcal for display (1 kJ ≈ 0.239 kcal)
        energy_kcal = int(energy_kj * 0.239)

        current = ('bike', cadence, power, energy_kj)
        if self.debug or current != self.last_values.get('bike'):
            print("FE Bike: cadence[%d] power[%dW] energy[%d kJ / %d kcal]" % (
                cadence, power, energy_kj, energy_kcal))
        self.last_values['bike'] = current

        self.send_broadcast_data(self.channel, data)
        self.wait_tx()


class HeartRateBroadcaster(AntBroadcaster):
    """Broadcasts heart rate data as an ANT+ HRM sensor."""

    def __init__(self, network_key, debug):
        AntBroadcaster.__init__(self, network_key, debug,
                                device_type=ANT_DEVICE_TYPE_HEART_RATE,
                                channel=1,
                                channel_period=ANT_HRM_CHANNEL_PERIOD)
        self.debug = debug
        self.beat_count = 0
        self.measurement_time = 0
        self.last_heart_rate = -1

    def broadcastHeartRate(self, heart_rate=0):
        """
        Broadcast heart rate data using ANT+ HRM profile Page 0.

        ANT+ HRM Page 0 format (8 bytes):
        - Byte 0: Data page number (0x00)
        - Bytes 1-3: Reserved (0xFF)
        - Bytes 4-5: Heart beat event time (1/1024 sec, uint16_le)
        - Byte 6: Heart beat count (uint8, rollover at 255)
        - Byte 7: Computed heart rate (uint8, 0-255 bpm)
        """
        # Update measurement time and beat count based on heart rate
        if heart_rate > 0:
            # Time between beats in 1/1024 second units
            beat_interval = int((60.0 / heart_rate) * 1024)
            self.measurement_time = (self.measurement_time + beat_interval) & 0xFFFF
            self.beat_count = (self.beat_count + 1) & 0xFF

        data = [
            0x00,  # Page 0 (basic HR data page)
            0xFF,  # Reserved
            0xFF,  # Reserved
            0xFF,  # Reserved
            self.measurement_time & 0xFF,         # Beat event time LSB
            (self.measurement_time >> 8) & 0xFF,  # Beat event time MSB
            self.beat_count,                      # Heart beat count
            int(heart_rate) & 0xFF                # Instant heart rate
        ]

        if self.debug or heart_rate != self.last_heart_rate:
            print("Sending HR data for device[%s]: %s for hr[%s]" % (
                self.deviceId, str(data), heart_rate))

        self.send_broadcast_data(self.channel, data)
        self.last_heart_rate = heart_rate
        self.wait_tx()


class SpeedBroadcaster(AntBroadcaster):
    """Broadcasts speed/distance data as an ANT+ Bike Speed sensor."""

    # Typical bike wheel circumference in meters (700x25c road tire)
    WHEEL_CIRCUMFERENCE = 2.105

    # Kettler distance unit in meters (typically 100m per unit, adjust if needed)
    KETTLER_DISTANCE_UNIT_METERS = 100

    def __init__(self, network_key, debug):
        AntBroadcaster.__init__(self, network_key, debug,
                                device_type=ANT_DEVICE_TYPE_SPEED,
                                channel=2,
                                channel_period=ANT_SPEED_CHANNEL_PERIOD)
        self.debug = debug
        self.measurement_time = 0
        self.last_speed = -1
        self.last_distance = -1

    def broadcastSpeed(self, speed_tenths_kmh=0, distance_kettler_units=0):
        """
        Broadcast speed/distance data using ANT+ Bike Speed profile.

        ANT+ Speed sensor format (8 bytes):
        - Bytes 0-3: Reserved (0xFF)
        - Bytes 4-5: Bike speed event time (1/1024 sec, uint16_le)
        - Bytes 6-7: Cumulative wheel revolutions (uint16_le)

        Args:
            speed_tenths_kmh: Speed in 0.1 km/h units (e.g., 250 = 25.0 km/h)
            distance_kettler_units: Distance in Kettler units (likely 100m per unit)
        """
        # Calculate cumulative wheel revolutions from Kettler distance
        # This ensures distance matches what Kettler reports
        distance_meters = distance_kettler_units * self.KETTLER_DISTANCE_UNIT_METERS
        cumulative_revs = distance_meters / self.WHEEL_CIRCUMFERENCE

        # Advance measurement time based on speed (for proper speed calculation by receiver)
        speed_ms = speed_tenths_kmh / 36.0  # Convert 0.1 km/h to m/s
        if speed_ms > 0:
            # Advance time by 0.25s in 1/1024 second units
            self.measurement_time = (self.measurement_time + 256) & 0xFFFF

        wheel_revs_int = int(cumulative_revs) & 0xFFFF  # 16-bit rollover

        data = [
            0xFF,  # Reserved
            0xFF,  # Reserved
            0xFF,  # Reserved
            0xFF,  # Reserved
            self.measurement_time & 0xFF,         # Event time LSB
            (self.measurement_time >> 8) & 0xFF,  # Event time MSB
            wheel_revs_int & 0xFF,                # Cumulative revs LSB
            (wheel_revs_int >> 8) & 0xFF          # Cumulative revs MSB
        ]

        if self.debug or speed_tenths_kmh != self.last_speed or distance_kettler_units != self.last_distance:
            print("Sending Speed data for device[%s]: %s speed[%.1f km/h] dist[%dm]" % (
                self.deviceId, str(data), speed_tenths_kmh / 10.0, distance_meters))

        self.send_broadcast_data(self.channel, data)
        self.last_speed = speed_tenths_kmh
        self.last_distance = distance_kettler_units
        self.wait_tx()
