import asyncio
from bleak import BleakScanner, BleakClient
import sys

UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E" # Da dove Python LEGGE
UART_TX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E" # Dove Python SCRIVE

class TerminalBLE:
    def __init__(self):
        self.client = None
        self.devices = []
        self.connected_device = None

    def notification_handler(self, sender, data):
        """Gestisce i dati in arrivo dall'ESP32"""
        try:
            print(f"\n[🟢 RICEVUTO]: {data.decode('utf-8').strip()}")
        except:
            print(f"\n[🟢 RAW]: {data}")
        print("Scelta: ", end="", flush=True) # Ricrea il prompt

    async def scan(self):
        print("\n🔎 Scansione in corso (5 secondi)...")
        try:
            discovered = await BleakScanner.discover(timeout=5.0)
            self.devices = [d for d in discovered if d.name]
            
            if not self.devices:
                print("❌ Nessun dispositivo trovato.")
                return

            print("\n📱 Dispositivi Trovati:")
            for i, d in enumerate(self.devices):
                print(f"  [{i}] {d.name} ({d.address})")
        except Exception as e:
            print(f"\n❌ Errore di scansione: {e}")

    async def connect(self, index):
        if index < 0 or index >= len(self.devices):
            print("❌ Indice non valido.")
            return

        device = self.devices[index]
        print(f"\n🔌 Connessione a {device.name} in corso...")
        
        self.client = BleakClient(device.address)
        try:
            await self.client.connect()
            self.connected_device = device
            print(f"✅ Connesso a {device.name}!")
            
            # Attiva le notifiche in background
            await self.client.start_notify(UART_RX_CHAR_UUID, self.notification_handler)
        except Exception as e:
            print(f"❌ Errore di connessione: {e}")

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            print("\n🛑 Disconnesso.")
            self.connected_device = None
        else:
            print("\n⚠️ Non eri connesso.")

    async def send(self, data):
        if not self.client or not self.client.is_connected:
            print("\n❌ Non sei connesso a nessun dispositivo.")
            return
        
        try:
            await self.client.write_gatt_char(UART_TX_CHAR_UUID, data.encode('utf-8'))
            print(f"[🔵 INVIATO]: {data.strip()}")
        except Exception as e:
            print(f"\n❌ Errore di invio: {e}")

    async def run(self):
        print("="*40)
        print(" ESP32 BLE TERMINAL CONTROLLER ")
        print("="*40)

        while True:
            # Menu
            print("\n--- MENU PRINCIPALE ---")
            stato = f"✅ {self.connected_device.name}" if self.connected_device else "❌ Disconnesso"
            print(f"Stato attuale: {stato}")
            print("1. Scansiona dispositivi")
            print("2. Connetti (scegli numero)")
            print("3. Invia 'LED_ON'")
            print("4. Invia 'LED_OFF'")
            print("5. Invia comando libero")
            print("6. Disconnetti")
            print("0. Esci")

            # asyncio.to_thread permette di usare input() senza bloccare il Bluetooth
            scelta = await asyncio.to_thread(input, "\nScelta: ")

            if scelta == '1':
                await self.scan()
            elif scelta == '2':
                if not self.devices:
                    print("⚠️ Fai prima una scansione!")
                    continue
                idx_str = await asyncio.to_thread(input, "Inserisci il numero del dispositivo (es. 0): ")
                if idx_str.isdigit():
                    await self.connect(int(idx_str))
            elif scelta == '3':
                await self.send("LED_ON\n")
            elif scelta == '4':
                await self.send("LED_OFF\n")
            elif scelta == '5':
                cmd = await asyncio.to_thread(input, "Scrivi il comando: ")
                await self.send(cmd + "\n")
            elif scelta == '6':
                await self.disconnect()
            elif scelta == '0':
                await self.disconnect()
                print("Uscita...")
                break
            else:
                print("Scelta non valida.")

if __name__ == "__main__":
    app = TerminalBLE()
    # Tutto gira in modo fluido su un solo thread asincrono
    asyncio.run(app.run())