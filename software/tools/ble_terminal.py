#!/usr/bin/env python3
"""
BLE Terminal - Connect to BLE UART devices (Nordic NUS)
Cross-platform BLE terminal program using bleak library.
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Try to import bleak, install if needed
try:
    import bleak
    from bleak import BleakScanner, BleakClient
except ImportError:
    print("Installing bleak library...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "bleak"])
    import bleak
    from bleak import BleakScanner, BleakClient
    from bleak.backends.characteristic import BleakCharacteristic

# Nordic UART Service (NUS) UUIDs
NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24d4179e"
NUS_TX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24d4179e"  # Write to device
NUS_RX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24d4179e"  # Read from device


class BLETerminal:
    def __init__(self):
        self.client = None
        self.rx_char = None
        self.connected = False
        self.running = True
        self.device_name = None

    async def scan(self, duration=5):
        """Scan for BLE devices."""
        print(f"\n{'='*60}")
        print(f"Scanning for BLE devices for {duration} seconds...")
        print(f"{'='*60}\n")
        
        devices = await BleakScanner.discover(timeout=duration)
        
        if not devices:
            print("No devices found.")
            return []
        
        # Filter and display devices
        print(f"{'#':<4} {'Name':<30} {'Address':<20} {'RSSI'}")
        print("-" * 60)
        
        for i, dev in enumerate(devices):
            name = dev.name or "Unknown"
            rssi = dev.rssi if hasattr(dev, 'rssi') else "N/A"
            print(f"{i+1:<4} {name:<30} {dev.address:<20} {rssi}")
        
        return devices

    async def connect(self, address):
        """Connect to a BLE device and discover NUS service."""
        print(f"\nConnecting to {address}...")
        
        try:
            self.client = BleakClient(address)
            await self.client.connect()
            
            # In bleak 1.x, services are accessed via .services after connection
            services = self.client.services
            
            # Find Nordic UART Service (works for both Nordic and ESP32)
            nus_service = None
            for svc in services:
                if svc.uuid.upper() == NUS_SERVICE_UUID.upper():
                    nus_service = svc
                    break
            
            if not nus_service:
                print("Warning: NUS service not found. Available services:")
                for svc in services:
                    print(f"  {svc.uuid}")
                # Try to continue anyway with manual characteristic lookup
                await self._find_nus_chars(services)
            else:
                print(f"Found NUS service: {nus_service.uuid}")
                for char in nus_service.characteristics:
                    if char.uuid.upper() == NUS_RX_CHAR_UUID.upper():
                        self.rx_char = char
                        await self.client.start_notify(char, self._notification_handler)
                        print(f"  RX Characteristic: {char.uuid}")
                    elif char.uuid.upper() == NUS_TX_CHAR_UUID.upper():
                        print(f"  TX Characteristic: {char.uuid}")
            
            # If no RX char found yet, search ALL characteristics for notify
            if not self.rx_char:
                print("Searching all characteristics for notify capability...")
                for svc in services:
                    for char in svc.characteristics:
                        props = getattr(char, 'properties', [])
                        is_notifiable = False
                        if isinstance(props, int):
                            is_notifiable = bool(props & 0x10)  # Notify property
                        elif isinstance(props, list):
                            is_notifiable = 'notify' in props or 'indicate' in props
                        
                        if is_notifiable:
                            self.rx_char = char
                            await self.client.start_notify(char, self._notification_handler)
                            print(f"  Found notify char: {char.uuid}")
                            break
                    if self.rx_char:
                        break
            
            self.connected = True
            print("Connected!")
            return True
            
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def _find_nus_chars(self, services):
        """Manually search for NUS characteristics if service not found."""
        for svc in services:
            for char in svc.characteristics:
                props = getattr(char, 'properties', [])
                is_notifiable = False
                if isinstance(props, int):
                    is_notifiable = bool(props & 0x10)  # Notify property
                elif isinstance(props, list):
                    is_notifiable = 'notify' in props or 'indicate' in props
                
                if char.uuid.upper() == NUS_RX_CHAR_UUID.upper():
                    self.rx_char = char
                    await self.client.start_notify(char, self._notification_handler)
                    print(f"Found RX char: {char.uuid}")
                elif char.uuid.upper() == NUS_TX_CHAR_UUID.upper():
                    print(f"Found TX char: {char.uuid}")
                elif is_notifiable and not self.rx_char:
                    # Also subscribe to any notify characteristic as fallback
                    self.rx_char = char
                    await self.client.start_notify(char, self._notification_handler)
                    print(f"Found notify char: {char.uuid}")

    def _notification_handler(self, characteristic, data):
        """Handle incoming data from BLE."""
        try:
            text = data.decode('utf-8')
            print(f"\n[RX] {text}")
            print("> ", end="", flush=True)
        except:
            # Print as hex if not valid UTF-8
            print(f"\n[RX hex] {data.hex()}")
            print("> ", end="", flush=True)

    async def disconnect(self):
        """Disconnect from BLE device."""
        if self.client:
            try:
                await self.client.disconnect()
            except:
                pass
        self.connected = False
        print("\nDisconnected.")

    async def send(self, data):
        """Send data to BLE device."""
        if not self.connected or not self.client:
            print("Not connected!")
            return
        
        try:
            # Find TX characteristic
            services = self.client.services
            tx_char = None
            
            for svc in services:
                for char in svc.characteristics:
                    if char.uuid.upper() == NUS_TX_CHAR_UUID.upper():
                        tx_char = char
                        break
                if tx_char:
                    break
            
            if tx_char:
                await self.client.write_gatt_char(tx_char, data.encode('utf-8'))
                print(f"[TX] {data}")
            else:
                # Try to write to any writable characteristic
                for svc in services:
                    for char in svc.characteristics:
                        # Check for write property - properties can be list or int
                        props = getattr(char, 'properties', [])
                        is_writable = False
                        if isinstance(props, int):
                            is_writable = bool(props & 0x04)  # Write property
                        elif isinstance(props, list):
                            is_writable = 'write' in props or 'write-without-response' in props
                        
                        if is_writable:
                            await self.client.write_gatt_char(char, data.encode('utf-8'))
                            print(f"[TX] {data}")
                            return
                print("No writable characteristic found!")
                
        except Exception as e:
            print(f"Send failed: {e}")


async def interactive_terminal(term: BLETerminal):
    """Run interactive terminal."""
    print("\n" + "="*60)
    print("BLE Terminal - Interactive Mode")
    print("="*60)
    print("Commands:")
    print("  - Type anything and press Enter to send")
    print("  - Type 'quit' or 'exit' to disconnect and exit")
    print("  - Type 'help' to show this help")
    print("="*60 + "\n")
    
    while term.connected and term.running:
        try:
            # Use asyncio to allow non-blocking input
            line = await asyncio.get_event_loop().run_in_executor(None, input, "> ")
            
            if line.lower() in ['quit', 'exit', 'q']:
                break
            elif line.lower() == 'help':
                print("\nCommands:")
                print("  - Type and send data to BLE device")
                print("  - quit/exit: Disconnect and exit")
                print("  - help: Show this help")
            elif line:
                await term.send(line)
                
        except EOFError:
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    await term.disconnect()


async def main():
    """Main entry point."""
    print("\n" + "="*60)
    print("BLE UART Terminal")
    print("Scans for BLE devices and connects to Nordic UART Service")
    print("="*60)
    
    term = BLETerminal()
    
    # Scan for devices
    devices = await term.scan(duration=5)
    
    if not devices:
        print("No devices found. Make sure BLE is enabled.")
        return
    
    # Ask user to select device
    print("\n" + "="*60)
    try:
        choice = input("Enter device number to connect (or 'r' to rescan, 'q' to quit): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    
    if choice.lower() == 'q':
        return
    
    if choice.lower() == 'r':
        devices = await term.scan(duration=5)
        choice = input("Enter device number to connect: ").strip()
    
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(devices):
            device = devices[idx]
            success = await term.connect(device.address)
            
            if success:
                await interactive_terminal(term)
        else:
            print("Invalid selection.")
    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")