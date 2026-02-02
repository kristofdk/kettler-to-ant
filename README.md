# Kettler ANT+ Adapter

This project makes a Kettler Racer 9 usable with any software requiring ANT+, such as Zwift or Sufferfest.

It reads power and cadence data from a Kettler indoor bike over USB (or Bluetooth) and broadcasts it via an ANT+ USB dongle.

## Requirements

- Python 3.8+ (tested with Python 3.14)
- ANT+ USB stick (Dynastream ANTUSB2 or ANTUSB-m recommended)
- Kettler indoor bike with serial interface

## Installation

```bash
pip install -r requirements.txt
```

### Linux

On Linux, you need to install udev rules for the ANT+ USB stick:

```bash
sudo python -m openant.udev_rules
```

### Dependencies

- [openant](https://github.com/Tigge/openant) - ANT+ communication library
- [pyserial](https://github.com/pyserial/pyserial) - Serial communication with Kettler bike

## Usage

Set the ANT+ network key as an environment variable (required):

```bash
export ANT_PLUS_NETWORK_KEY="B9 A5 21 FB BD 72 C3 45"
```

The standard ANT+ network key can be obtained from [thisisant.com](https://www.thisisant.com/developer/ant-plus/ant-plus-basics/network-keys).

Then run:

```bash
python kettler_ant_adapter.py
```

The adapter will:
1. Auto-detect your Kettler bike on any available USB serial port
2. Auto-detect your ANT+ USB stick
3. Broadcast power and cadence data as an ANT+ power meter

## Platform Support

- **Linux** - Full support (Raspberry Pi, Ubuntu, etc.)
- **macOS** - Full support
- **Windows** - Full support

## Project Structure

```
├── kettler_ant_adapter.py    # Main entry point
├── components/
│   ├── ant.py                # PowerModel data class
│   ├── ant_broadcaster.py    # ANT+ power meter broadcaster
│   ├── ant_writer.py         # ANT+ transmission handler
│   └── kettler_serial.py     # Kettler serial communication
└── ant_support/
    ├── ant.py                # ANT+ protocol (openant wrapper)
    ├── ant_messages.py       # ANT message definitions
    ├── ant_sport_messages.py # ANT+ sport message definitions
    └── message_set.py        # Message parsing framework
```

## Troubleshooting

### ANT+ USB stick not detected

- Ensure the USB stick is plugged in
- On Linux, verify udev rules are installed: `sudo python -m openant.udev_rules`
- Check USB permissions or run with sudo

### Kettler not detected

- Check that the Kettler is powered on and connected via USB
- The adapter scans for USB serial devices automatically
- On Linux, you may need to add your user to the `dialout` group:
  ```bash
  sudo usermod -a -G dialout $USER
  ```

### Network key error

- Ensure `ANT_PLUS_NETWORK_KEY` environment variable is set
- Format: space-separated hex pairs (e.g., "B9 A5 21 FB BD 72 C3 45")

### Windows: USB timeout errors (libusb0)

If you see errors like `libusb0-dll:err [_usb_reap_async] timeout error`, the issue is that pyusb is using the old libusb0 backend instead of libusb1.

**Fix:**

1. Install the WinUSB driver for your ANT+ stick using [Zadig](https://zadig.akeo.ie/):
   - Run Zadig as Administrator
   - Go to **Options → List All Devices**
   - Select your ANT+ USB stick
   - Change driver to **WinUSB**
   - Click "Replace Driver"

2. Copy the libusb-1.0.dll to where Python can find it:
   ```bash
   python -c "import shutil; shutil.copy(r'.venv\Lib\site-packages\libusb\_platform\windows\x86_64\libusb-1.0.dll', r'.venv\Scripts\libusb-1.0.dll')"
   ```

3. Verify libusb1 is now available:
   ```bash
   python -c "import usb.backend.libusb1 as l1; print('libusb1:', l1.get_backend())"
   ```
   You should see a `_LibUSB object` instead of `None`.
