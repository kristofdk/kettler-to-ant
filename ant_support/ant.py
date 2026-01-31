#!/usr/bin/env python3
"""
ANT+ communication module using openant library.

This module provides a wrapper around openant that maintains backward
compatibility with the original serial-based implementation.
"""

import sys
import time
import threading
from functools import reduce

from openant.easy.node import Node
from openant.easy.channel import Channel

# ANT message type constants (kept for backward compatibility)
ANT_Version = 0x3e
ANT_Capabilities = 0x54
ANT_Channel_Status = 0x52
ANT_Channel_ID = 0x51

ANT_Request_Message = 0x4d
ANT_Unassign_Channel = 0x41
ANT_Assign_Channel = 0x42
ANT_Reset_System = 0x4a
ANT_Broadcast_Data = 0x4e
ANT_Acknowledged_Data = 0x4f
ANT_Extended_Acknowledged_Data = 0x5e
ANT_Extended_Burst_Data = 0x5f
ANT_Burst_Data = 0x50
ANT_Set_Network = 0x46
ANT_Set_Channel_ID = 0x51
ANT_Set_Channel_Period = 0x43
ANT_Set_Channel_Freq = 0x45
ANT_Open_Channel = 0x4b
ANT_Open_Scan_Channel = 0x5b
ANT_Close_Channel = 0x4c
ANT_Set_Channel_Search_Timeout = 0x44
ANT_Set_LP_Search_Timeout = 0x63
ANT_Set_Proximity_Search = 0x71
ANT_Init_Test_Mode = 0x53
ANT_Set_Test_Mode = 0x48
ANT_Enable_Ext_Msgs = 0x66
ANT_Lib_Config = 0x6E
ANTRCT_Set_RSSI_Threshold = 0xC4

ant_ids = {}
for ant_message in [x for x in dir() if x.startswith('ANT')]:
    ant_ids[eval(ant_message)] = ant_message


# Exception classes (kept for backward compatibility)
class AntException(Exception):
    pass


class AntNoDataException(AntException):
    pass


class AntWrongResponseException(AntException):
    pass


class AntRxSearchTimeoutException(AntException):
    pass


class AntResponseTimeoutException(AntException):
    pass


class AntBurstFailedError(AntException):
    pass


class AntBurstSequenceError(AntException):
    pass


class AntTransferRxFailedException(AntException):
    pass


class AntChecksumException(AntException):
    pass


def load_ant_messages():
    """Load ANT message definitions for message parsing."""
    from . import ant_messages
    try:
        from . import quarq_messages
    except ImportError:
        quarq_messages = None

    from . import ant_sport_messages

    messages = ant_sport_messages.messages
    if quarq_messages:
        messages += quarq_messages.messages
    messages += ant_messages.messages

    offending_messages = ['heart_rate', 'speed', 'cadence', 'speed_cadence']
    for m in offending_messages:
        messages.messages_keys.remove(m)
        messages.messages_keys.append(m)

    return messages


class Ant:
    """
    ANT+ communication class using openant library.

    This class provides a compatible interface with the original serial-based
    implementation while using openant for USB communication.
    """

    def __init__(self, quiet=False, silent=False):
        self.quiet = quiet
        self.silent = silent
        self.messages = load_ant_messages()
        self.t0 = time.time()

        self._node = None
        self._channels = {}
        self._network_keys = {}
        self._running = False
        self._node_thread = None

        # Legacy compatibility attributes
        self.rssi_log = {}
        self.rssi_logging = False

        # Simulated serial port attributes for compatibility
        self.sp = self._SerialPortCompat(self)

    class _SerialPortCompat:
        """Compatibility shim for code that accesses self.sp directly."""
        def __init__(self, parent):
            self._parent = parent
            self.timeout = 30
            self.baudrate = 115200

        def setTimeout(self, t):
            self.timeout = t

        def flushInput(self):
            pass

        def flushOutput(self):
            pass

        def flush(self):
            pass

        def inWaiting(self):
            return 0

        def getCTS(self):
            return True

    def auto_init(self):
        """Initialize the ANT+ USB device automatically."""
        if self._node is not None:
            return

        try:
            self._node = Node()
            self._node_thread = threading.Thread(target=self._node.start, daemon=True)
            self._node_thread.start()
            self._running = True

            # Give the node time to initialize
            time.sleep(0.5)

            if not self.quiet:
                print("ANT+ USB device initialized via openant")
        except Exception as e:
            raise Exception(f"Failed to initialize ANT+ USB device: {e}")

    def serial_init(self, port=None):
        """Initialize ANT device (uses auto_init with openant)."""
        self.auto_init()

    def network_init(self, port=None):
        """Initialize ANT device (uses auto_init with openant)."""
        self.auto_init()

    def assign_channel(self, channel, type, network, extended=None):
        """Assign and configure an ANT channel."""
        if self._node is None:
            self.auto_init()

        # Create channel - type 0x10 is transmit master
        channel_type = Channel.Type.BIDIRECTIONAL_TRANSMIT

        try:
            ant_channel = self._node.new_channel(channel_type, network)
            self._channels[channel] = ant_channel

            if not self.quiet:
                print(f"Assigned channel {channel} as type {type} on network {network}")
        except Exception as e:
            raise AntWrongResponseException(f"Failed to assign channel: {e}")

    def unassign_channel(self, channel):
        """Unassign an ANT channel."""
        if channel in self._channels:
            try:
                self._node.remove_channel(self._channels[channel])
                del self._channels[channel]
            except Exception as e:
                raise AntWrongResponseException(f"Failed to unassign channel: {e}")

    def set_network_key(self, network, key):
        """Set the network key for a given network number."""
        if self._node is None:
            self.auto_init()

        # Convert key list to bytes if necessary
        if isinstance(key, list):
            key = bytes(key)

        try:
            self._node.set_network_key(network, key)
            self._network_keys[network] = key

            if not self.quiet:
                print(f"Set network key for network {network}")
        except Exception as e:
            raise AntWrongResponseException(f"Failed to set network key: {e}")

    def set_channel_id(self, channel, device, device_type_id, man_id):
        """Set the channel ID (device number, type, and transmission type)."""
        if channel not in self._channels:
            raise AntWrongResponseException(f"Channel {channel} not assigned")

        try:
            self._channels[channel].set_id(device, device_type_id, man_id)

            if not self.quiet:
                print(f"Set channel {channel} ID: device={device}, type={device_type_id}, man={man_id}")
        except Exception as e:
            raise AntWrongResponseException(f"Failed to set channel ID: {e}")

    def set_channel_period(self, channel, period):
        """Set the channel message period."""
        if channel not in self._channels:
            raise AntWrongResponseException(f"Channel {channel} not assigned")

        try:
            self._channels[channel].set_period(period)

            if not self.quiet:
                print(f"Set channel {channel} period: {period}")
        except Exception as e:
            raise AntWrongResponseException(f"Failed to set channel period: {e}")

    def set_channel_freq(self, channel, freq):
        """Set the channel RF frequency."""
        if channel not in self._channels:
            raise AntWrongResponseException(f"Channel {channel} not assigned")

        try:
            self._channels[channel].set_rf_freq(freq)

            if not self.quiet:
                print(f"Set channel {channel} frequency: {freq}")
        except Exception as e:
            raise AntWrongResponseException(f"Failed to set channel frequency: {e}")

    def set_channel_search_timeout(self, channel, search_timeout):
        """Set the channel search timeout."""
        if channel not in self._channels:
            raise AntWrongResponseException(f"Channel {channel} not assigned")

        try:
            self._channels[channel].set_search_timeout(search_timeout)

            if not self.quiet:
                print(f"Set channel {channel} search timeout: {search_timeout}")
        except Exception as e:
            raise AntWrongResponseException(f"Failed to set search timeout: {e}")

    def set_low_priority_search_timeout(self, channel, search_timeout):
        """Set the low priority search timeout (may not be supported by all devices)."""
        # openant may not support this directly, log warning
        if not self.quiet:
            print(f"Low priority search timeout set to {search_timeout} (may not be supported)")

    def set_proximity_search(self, channel, level):
        """Set proximity search level (may not be supported by all devices)."""
        if not self.quiet:
            print(f"Proximity search level set to {level} (may not be supported)")

    def open_channel(self, channel):
        """Open an ANT channel for communication."""
        if channel not in self._channels:
            raise AntWrongResponseException(f"Channel {channel} not assigned")

        try:
            self._channels[channel].open()

            if not self.quiet:
                print(f"Opened channel {channel}")
        except Exception as e:
            raise AntWrongResponseException(f"Failed to open channel: {e}")

    def close_channel(self, channel):
        """Close an ANT channel."""
        if channel not in self._channels:
            raise AntWrongResponseException(f"Channel {channel} not assigned")

        try:
            self._channels[channel].close()

            if not self.quiet:
                print(f"Closed channel {channel}")
        except Exception as e:
            raise AntWrongResponseException(f"Failed to close channel: {e}")

    def send_broadcast_data(self, chan, data):
        """Send broadcast data on a channel."""
        if chan not in self._channels:
            raise AntWrongResponseException(f"Channel {chan} not assigned")

        # Convert data list to bytes if necessary
        if isinstance(data, list):
            data = bytes(data)

        try:
            self._channels[chan].send_broadcast_data(data)

            if not self.quiet:
                print(f"Sent broadcast on channel {chan}: {[hex(b) for b in data]}")
        except Exception as e:
            raise AntException(f"Failed to send broadcast data: {e}")

    def send_acknowledged_data(self, chan, data):
        """Send acknowledged data on a channel."""
        if chan not in self._channels:
            raise AntWrongResponseException(f"Channel {chan} not assigned")

        if isinstance(data, list):
            data = bytes(data)

        try:
            self._channels[chan].send_acknowledged_data(data)

            if not self.quiet:
                print(f"Sent acknowledged data on channel {chan}")
        except Exception as e:
            raise AntException(f"Failed to send acknowledged data: {e}")

    def send_burst_data(self, chan, data, progress_func=None, broadcast_messages=[]):
        """Send burst data on a channel."""
        if chan not in self._channels:
            raise AntWrongResponseException(f"Channel {chan} not assigned")

        if isinstance(data, list):
            data = bytes(data)

        try:
            self._channels[chan].send_burst_transfer(data)

            if not self.quiet:
                print(f"Sent burst data on channel {chan}")
        except Exception as e:
            raise AntBurstFailedError(f"Failed to send burst data: {e}")

    def receive_message(self, source=None, dispose=None, wait=30.0, syncprint=''):
        """
        Receive a message from the ANT device.

        Note: With openant, message handling is done through callbacks.
        This method provides basic compatibility but may not work for all use cases.
        """
        # openant handles messages through callbacks on the channel
        # This is a compatibility stub that waits and returns None
        time.sleep(min(wait, 0.1))
        return None

    def wait_for_response(self, responses, timeout):
        """
        Wait for specific ANT responses.

        Note: With openant, this is handled internally by the library.
        """
        time.sleep(min(timeout, 0.1) if timeout else 0.1)
        return None

    def flush(self):
        """Flush any pending data."""
        pass

    def flush_msg_queue(self):
        """Flush the message queue."""
        pass

    def enable_rssi_logging(self, onoff):
        """Enable or disable RSSI logging."""
        self.rssi_logging = onoff

    def enable_extended_messages(self, enable):
        """Enable extended messages (may not be supported)."""
        if not self.quiet:
            print(f"Extended messages {'enabled' if enable else 'disabled'}")

    def config_extended_messages(self, rssi=False, rx_timestamp=False, chan_id=False):
        """Configure extended messages (may not be supported)."""
        pass

    def get_capabilities(self):
        """Get ANT device capabilities."""
        if self._node is None:
            self.auto_init()

        try:
            return self._node.get_capabilities()
        except Exception as e:
            raise AntException(f"Failed to get capabilities: {e}")

    def stop(self):
        """Stop the ANT node."""
        if self._node is not None:
            try:
                # Close all channels first
                for channel in list(self._channels.keys()):
                    try:
                        self.close_channel(channel)
                    except:
                        pass

                self._node.stop()
                self._running = False

                if not self.quiet:
                    print("ANT+ node stopped")
            except Exception as e:
                if not self.quiet:
                    print(f"Error stopping ANT+ node: {e}")

    def __del__(self):
        """Cleanup when the object is destroyed."""
        self.stop()


def quicktest():
    """Quick test of ANT+ functionality."""
    a = Ant()
    a.auto_init()
    print(a.get_capabilities())


if __name__ == "__main__":
    quicktest()
