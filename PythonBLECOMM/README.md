# BLE Terminal

A cross-platform command-line BLE terminal program that scans for BLE devices and connects to BLE UART emulators (Nordic NUS).

## Requirements

- Python 3.8+
- bleak library

## Installation

```bash
cd PythonBLECOMM
pip install -r requirements.txt
```

## Usage

```bash
python ble_terminal.py
```

### Features

1. **Scan** - Automatically scans for 5 seconds and lists all nearby BLE devices
2. **Select** - Enter the device number to connect
3. **Connect** - Connects to the selected device using Nordic UART Service (NUS)
4. **Interactive Mode** - Type messages to send, received data is displayed automatically

### Commands in Interactive Mode

- **Type and press Enter** - Send data to BLE device
- `quit` / `exit` / `q` - Disconnect and exit
- `help` - Show help

### Nordic UART Service UUIDs

- Service: `6e400001-b5a3-f393-e0a9-e50e24d4179e`
- TX (Write): `6e400002-b5a3-f393-e0a9-e50e24d4179e`
- RX (Notify): `6e400003-b5a3-f393-e0a9-e50e24d4179e`

## Platform Notes

### macOS
- May need to grant Bluetooth permissions in System Preferences
- Works with native CoreBluetooth (handled by bleak)

### Linux
- May need to install BlueZ: `sudo apt install bluez`
- May need to run with sudo or add user to bluetooth group

### Windows
- Works natively with Windows BLE API
- May need to install Bluetooth LE Enumerator from Windows Update