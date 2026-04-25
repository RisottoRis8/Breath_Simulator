import flet as ft
import asyncio
from bleak import BleakScanner, BleakClient

# UUID standard del servizio Nordic UART
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"

async def main(page: ft.Page):
    page.title = "ESP32 BLE Controller"
    page.window.width = 600
    page.window.height = 700
    page.theme_mode = ft.ThemeMode.LIGHT 
    
    client_ble = [None] 
    
    # --- ELEMENTI DELLA GUI ---
    status_text = ft.Text("Stato: Disconnesso", color=ft.Colors.RED, weight=ft.FontWeight.BOLD)
    log_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    device_dropdown = ft.Dropdown(width=250, label="Dispositivi")
    
    def gui_log(msg, color=ft.Colors.BLACK):
        log_list.controls.append(ft.Text(msg, color=color))
        page.update()

    # --- FUNZIONI BLUETOOTH ---
    async def scan_click(e):
        scan_btn.disabled = True
        page.update()
        gui_log("🔎 Scansione in corso (5s)...", ft.Colors.BLUE)
        try:
            devices = await BleakScanner.discover(timeout=5.0)
            device_dropdown.options.clear()
            for d in devices:
                if d.name:
                    device_dropdown.options.append(ft.dropdown.Option(text=f"{d.name} ({d.address})", key=d.address))
            gui_log(f"✅ Trovati {len(device_dropdown.options)} dispositivi.")
            if device_dropdown.options:
                device_dropdown.value = device_dropdown.options[0].key
        except Exception as ex:
            gui_log(f"❌ Errore scansione: {ex}", ft.Colors.RED)
        scan_btn.disabled = False
        page.update()

    async def notification_handler(sender, data):
        try:
            msg = data.decode('utf-8').strip()
            gui_log(f"🟢 [ESP32]: {msg}", ft.Colors.GREEN_700)
        except:
            gui_log(f"🟢 [ESP32 RAW]: {data}", ft.Colors.GREEN_700)

    async def connect_click(e):
        if not device_dropdown.value:
            gui_log("⚠️ Seleziona un dispositivo!", ft.Colors.ORANGE)
            return
        
        gui_log(f"🔌 Connessione a {device_dropdown.value}...")
        client_ble[0] = BleakClient(device_dropdown.value)
        try:
            await client_ble[0].connect()
            status_text.value = "Stato: Connesso"
            status_text.color = ft.Colors.GREEN
            connect_btn.disabled = True
            disconnect_btn.disabled = False
            gui_log("✅ Connesso!", ft.Colors.GREEN)
            await client_ble[0].start_notify(UART_RX_CHAR_UUID, notification_handler)
        except Exception as ex:
            gui_log(f"❌ Errore connessione: {ex}", ft.Colors.RED)
        page.update()

    async def disconnect_click(e):
        if client_ble[0] and client_ble[0].is_connected:
            gui_log("🛑 Disconnessione in corso...")
            try:
                await client_ble[0].disconnect()
                status_text.value = "Stato: Disconnesso"
                status_text.color = ft.Colors.RED
                connect_btn.disabled = False
                disconnect_btn.disabled = True
                gui_log("✅ Disconnesso correttamente.", ft.Colors.BLUE_GREY)
            except Exception as ex:
                gui_log(f"❌ Errore disconnessione: {ex}", ft.Colors.RED)
        page.update()

    async def send_cmd(cmd):
        if client_ble[0] and client_ble[0].is_connected:
            try:
                await client_ble[0].write_gatt_char(UART_TX_CHAR_UUID, cmd.encode('utf-8'), response=True)
                gui_log(f"🔵 [INVIATO]: {cmd.strip()}", ft.Colors.BLUE_700)
            except Exception as ex:
                gui_log(f"❌ Errore invio: {ex}", ft.Colors.RED)
        else:
            gui_log("⚠️ Non connesso!", ft.Colors.ORANGE)

    # --- BOTTONI ---
    scan_btn = ft.ElevatedButton("1. Scansiona", icon=ft.Icons.SEARCH, on_click=scan_click)
    connect_btn = ft.ElevatedButton("2. Connetti", icon=ft.Icons.BLUETOOTH, on_click=connect_click)
    disconnect_btn = ft.ElevatedButton("Disconnetti", icon=ft.Icons.BLUETOOTH_DISABLED, on_click=disconnect_click, disabled=True)
    
    # --- WRAPPER DEI COMANDI ---
    # Creiamo funzioni asincrone vere: Flet le gestirà automaticamente nel loop corretto!
    async def btn_led_on(e):
        await send_cmd("LED_ON\n")

    async def btn_led_off(e):
        await send_cmd("LED_OFF\n")

    async def btn_ping(e):
        await send_cmd("PING\n")
        
    async def btn_read(e):
        await send_cmd("Read\n")

    async def btn_send_custom(e):
        # Legge il testo, controlla che non sia vuoto
        if custom_input.value != "":
            # Aggiunge \n alla fine (l'ESP32 di solito lo richiede per capire che il comando è finito)
            await send_cmd(custom_input.value + "\n")
            
            # (Opzionale) Svuota la casella di testo dopo aver inviato
            custom_input.value = ""
            page.update()


    # --CAMPO DI SCRITTA --
    # Il campo dove scrivi. on_submit permette di inviare premendo "Invio" sulla tastiera!
    custom_input = ft.TextField(label="Scrivi un comando...", expand=True, on_submit=btn_send_custom)
    
    # Raggruppiamo la casella di testo e il bottone "Invia" in una singola riga
    custom_cmd_row = ft.Row([
        custom_input,
        ft.ElevatedButton("Invia", icon=ft.Icons.SEND, on_click=btn_send_custom)
    ])

    # --- BOTTONI ---
    scan_btn = ft.ElevatedButton("1. Scansiona", icon=ft.Icons.SEARCH, on_click=scan_click)
    connect_btn = ft.ElevatedButton("2. Connetti", icon=ft.Icons.BLUETOOTH, on_click=connect_click)
    disconnect_btn = ft.ElevatedButton("Disconnetti", icon=ft.Icons.BLUETOOTH_DISABLED, on_click=disconnect_click, disabled=True)
    
    # Ora passiamo le funzioni in modo pulito, senza lambda e senza create_task
    commands_row = ft.Row([
        ft.ElevatedButton("LED ON", bgcolor=ft.Colors.GREEN_100, on_click=btn_led_on),
        ft.ElevatedButton("LED OFF", bgcolor=ft.Colors.RED_100, on_click=btn_led_off),
        ft.ElevatedButton("PING", icon=ft.Icons.SEND, on_click=btn_ping),
        ft.ElevatedButton("Read", icon=ft.Icons.SEND, on_click=btn_read)
    ])

    log_container = ft.Container(content=log_list, border=ft.border.all(1, ft.Colors.OUTLINE), border_radius=10, padding=10, expand=True)

    # Aggiunge tutto alla pagina visibile
    page.add(
        ft.Text("Pannello di Controllo ESP32", size=24, weight=ft.FontWeight.BOLD),
        ft.Row([scan_btn, device_dropdown]),
        ft.Row([connect_btn, disconnect_btn]),
        ft.Divider(),
        ft.Text("Comandi Rapidi", size=16, weight=ft.FontWeight.W_500),
        commands_row,
        
        # --- LA TUA NUOVA RIGA QUI ---
        ft.Text("Comando Personalizzato", size=16, weight=ft.FontWeight.W_500),
        custom_cmd_row,
        # ----------------------------
        
        ft.Divider(),
        log_container,
        status_text
    )

if __name__ == "__main__":
    ft.app(target=main)