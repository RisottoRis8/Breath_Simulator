import flet as ft
import asyncio
import csv
from datetime import datetime
from bleak import BleakScanner, BleakClient

# UUID standard per la comunicazione seriale dell'HM-10
HM10_UART_CHAR_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"
UART_RX_CHAR_UUID = HM10_UART_CHAR_UUID
UART_TX_CHAR_UUID = HM10_UART_CHAR_UUID

MAX_POINTS = 200      # Numero massimo di segnali tracciati sul grafico
MAX_LOG_LINES = 200   # Numero massimo di righe nel terminale integrato

async def main(page: ft.Page):
    page.title = "HM-10 BLE Controller & Datalogger"
    page.window.width = 980
    page.window.height = 720
    page.theme_mode = ft.ThemeMode.LIGHT

    client_ble = [None]
    ble_buffer = "" # Buffer per ricomporre i pacchetti Bluetooth spezzati
    
    pressure_state = {
        "collecting": False,
        "logging_csv": False,
        "csv_file": None,
        "csv_writer": None,
        "total_points_received": 0,
        "points": [],
        "avg": None,
    }

    # --- ELEMENTI DELLA GUI ---
    status_text = ft.Text("Stato: Disconnesso", color=ft.Colors.RED, weight=ft.FontWeight.BOLD)
    log_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
    device_dropdown = ft.Dropdown(width=250, label="Dispositivi")
    avg_pressure_text = ft.Text("Media Pressione: -- Pa", size=14, weight=ft.FontWeight.BOLD)
    avg_pressure_box = ft.Container(
        content=avg_pressure_text,
        border=ft.border.all(1, ft.Colors.BLUE_GREY),
        border_radius=10,
        padding=10,
        width=260,
    )

    # --- FUNZIONE LOG OTTIMIZZATA ---
    def gui_log(msg, color=ft.Colors.BLACK, update_page=True):
        log_list.controls.append(ft.Text(msg, color=color))
        
        # Mantiene il terminale leggero eliminando i vecchi messaggi
        if len(log_list.controls) > MAX_LOG_LINES:
            log_list.controls.pop(0)
            
        if update_page:
            page.update()

    # --- GESTIONE DINAMICA ASSE X (Sliding Window) ---
    def update_x_axis(current_min_x, current_max_x):
        pressure_chart.min_x = current_min_x
        pressure_chart.max_x = current_max_x
        window_size = current_max_x - current_min_x
        step = 1
        if window_size > 20: step = 2
        if window_size > 50: step = 5
            
        new_x_labels = []
        start_tick = int(current_min_x)
        end_tick = int(current_max_x) + 1
        for i in range(start_tick, end_tick, step):
            if current_min_x <= i <= current_max_x:
                new_x_labels.append(
                    ft.ChartAxisLabel(i, label=ft.Text(str(i), size=11, color=ft.Colors.GREY_700))
                )
        pressure_chart.bottom_axis.labels = new_x_labels

    # --- INIZIALIZZAZIONE / CHIUSURA CSV ---
    def start_csv_log():
        filename = datetime.now().strftime("pressure_log_%Y%m%d_%H%M%S.csv")
        try:
            f = open(filename, mode='w', newline='')
            writer = csv.writer(f)
            writer.writerow(["Timestamp_s", "Pressione_Pa"]) # Intestazione
            pressure_state["csv_file"] = f
            pressure_state["csv_writer"] = writer
            pressure_state["logging_csv"] = True
            gui_log(f"📁 Log CSV avviato: {filename}", ft.Colors.BLUE)
        except Exception as ex:
            gui_log(f"❌ Errore creazione CSV: {ex}", ft.Colors.RED)

    def stop_csv_log():
        if pressure_state["logging_csv"] and pressure_state["csv_file"]:
            pressure_state["csv_file"].close()
            pressure_state["csv_file"] = None
            pressure_state["csv_writer"] = None
            pressure_state["logging_csv"] = False
            gui_log("🛑 Log CSV salvato e chiuso.", ft.Colors.BLUE)

    # --- GESTIONE RICEZIONE DATI ---
    async def notification_handler(sender, data):
        nonlocal ble_buffer # Permette di usare il buffer globale
        try:
            # Aggiungiamo i dati raw al buffer
            ble_buffer += data.decode('utf-8')
            
            # Processiamo solo quando troviamo una riga completa
            while '\n' in ble_buffer:
                line, ble_buffer = ble_buffer.split('\n', 1)
                msg = line.strip()
                
                if not msg:
                    continue
                
                # PARSER PER IL FORMATO "P: x Pa"
                if msg.startswith("P:"):
                    parts = msg.split()
                    if len(parts) >= 3 and parts[2] == "Pa":
                        try:
                            # Prende il valore della pressione
                            pressure = float(parts[1])
                            
                            # Calcola i secondi (assumendo un pacchetto ogni 10ms -> 100Hz)
                            time_s = pressure_state["total_points_received"] * 0.010 
                            
                            # 1. Scrivi SEMPRE sul CSV in tempo reale
                            if pressure_state["logging_csv"] and pressure_state["csv_writer"]:
                                pressure_state["csv_writer"].writerow([f"{time_s:.3f}", pressure])
                            
                            # 2. Aggiorna i dati in memoria per il grafico
                            pressure_state["total_points_received"] += 1
                            pressure_state["points"].append(
                                ft.LineChartDataPoint(x=time_s, y=pressure)
                            )
                            
                            if len(pressure_state["points"]) > MAX_POINTS:
                                pressure_state["points"].pop(0)
                            
                            # 3. Aggiorna la GUI SOLO ogni 10 messaggi (Throttling ~10Hz)
                            if pressure_state["total_points_received"] % 10 == 0:
                                gui_log(f"🟢 [DATA]: {msg}", ft.Colors.GREEN_700, update_page=False)

                                oldest_x = pressure_state["points"][0].x
                                newest_x = max(oldest_x + 5.0, time_s)
                                update_x_axis(oldest_x, newest_x)
                                
                                pressure_chart.data_series[0].data_points = pressure_state["points"]
                                
                                avg = sum(p.y for p in pressure_state["points"]) / len(pressure_state["points"])
                                pressure_state["avg"] = avg
                                avg_pressure_text.value = f"Media (ultimi 200): {avg:.2f} Pa"
                                
                                # Forza il salvataggio fisico su disco del CSV ogni 100 punti (1 secondo)
                                if pressure_state["total_points_received"] % 100 == 0 and pressure_state["csv_file"]:
                                    pressure_state["csv_file"].flush()

                                page.update()
                                
                        except ValueError:
                            pass # Ignora errori di conversione se la stringa è corrotta
                else:
                    # Stampa sempre i messaggi non-dati (es. messaggi di errore o log dal microcontrollore)
                    gui_log(f"💬 [HM-10]: {msg}", ft.Colors.BLUE_GREY)

        except Exception:
            pass

    # --- COMANDI BLUETOOTH ---
    async def send_cmd(cmd):
        cmd = cmd.strip()
        if cmd == "": return
        cmd_to_send = cmd + "\r\n"
        if client_ble[0] and client_ble[0].is_connected:
            try:
                await client_ble[0].write_gatt_char(UART_TX_CHAR_UUID, cmd_to_send.encode('utf-8'), response=False)
                gui_log(f"🔵 [INVIATO]: {cmd}", ft.Colors.BLUE_700)
            except Exception as ex:
                gui_log(f"❌ Errore invio: {ex}", ft.Colors.RED)
        else:
            gui_log("⚠️ Non connesso!", ft.Colors.ORANGE)

    # --- GESTIONE BOTTONI ---
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

    async def connect_click(e):
        if not device_dropdown.value:
            gui_log("⚠️ Seleziona un dispositivo!", ft.Colors.ORANGE)
            return
        gui_log(f"🔌 Connessione a {device_dropdown.value}...")
        client_ble[0] = BleakClient(device_dropdown.value)
        try:
            await client_ble[0].connect()
            await client_ble[0].start_notify(UART_RX_CHAR_UUID, notification_handler)
            status_text.value = "Stato: Connesso"
            status_text.color = ft.Colors.GREEN
            connect_btn.disabled = True
            disconnect_btn.disabled = False
            start_btn.disabled = False
            gui_log("✅ Connesso e in ascolto!", ft.Colors.GREEN)
        except Exception as ex:
            gui_log(f"❌ Errore connessione: {ex}", ft.Colors.RED)
        page.update()

    async def disconnect_click(e):
        if client_ble[0] and client_ble[0].is_connected:
            stop_csv_log() # Ferma il log se in corso
            gui_log("🛑 Disconnessione in corso...")
            try:
                await client_ble[0].disconnect()
                status_text.value = "Stato: Disconnesso"
                status_text.color = ft.Colors.RED
                connect_btn.disabled = False
                disconnect_btn.disabled = True
                start_btn.disabled = True
                stop_btn.disabled = True
                gui_log("✅ Disconnesso correttamente.", ft.Colors.BLUE_GREY)
            except Exception as ex:
                gui_log(f"❌ Errore disconnessione: {ex}", ft.Colors.RED)
        page.update()

    async def btn_start_measurement(e):
        pressure_state["collecting"] = True
        pressure_state["total_points_received"] = 0
        pressure_state["points"].clear()
        
        # Resetta grafico graficamente
        update_x_axis(0.0, 5.0)
        
        start_csv_log()
        await send_cmd("START")
        
        start_btn.disabled = True
        stop_btn.disabled = False
        page.update()

    async def btn_stop_measurement(e):
        pressure_state["collecting"] = False
        await send_cmd("STOP")
        stop_csv_log()
        
        start_btn.disabled = False
        stop_btn.disabled = True
        page.update()

    async def btn_send_custom(e):
        cmd = custom_input.value.strip().lstrip('.').strip()
        if cmd != "":
            await send_cmd(cmd)
            custom_input.value = ""
            page.update()

    # --- COMPONENTI UI ---
    scan_btn = ft.ElevatedButton("1. Scansiona", icon=ft.Icons.SEARCH, on_click=scan_click)
    connect_btn = ft.ElevatedButton("2. Connetti", icon=ft.Icons.BLUETOOTH, on_click=connect_click)
    disconnect_btn = ft.ElevatedButton("Disconnetti", icon=ft.Icons.BLUETOOTH_DISABLED, on_click=disconnect_click, disabled=True)

    # Tasti Start/Stop
    start_btn = ft.ElevatedButton("START Misura", icon=ft.Icons.PLAY_ARROW, bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE, on_click=btn_start_measurement, disabled=True)
    stop_btn = ft.ElevatedButton("STOP Misura", icon=ft.Icons.STOP, bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE, on_click=btn_stop_measurement, disabled=True)

    custom_input = ft.TextField(label="Comando libero...", expand=True, on_submit=btn_send_custom)
    
    y_axis_labels = []
    for val in range(-560, 561, 140):
        y_axis_labels.append(ft.ChartAxisLabel(val, label=ft.Text(str(val), size=11, color=ft.Colors.GREY_700)))

    x_axis_labels = []
    for i in range(6):
        x_axis_labels.append(ft.ChartAxisLabel(i, label=ft.Text(str(i), size=11, color=ft.Colors.GREY_700)))

    pressure_chart = ft.LineChart(
        data_series=[
            ft.LineChartData(data_points=[], color=ft.Colors.BLUE, curved=True, stroke_width=2, point=False)
        ],
        width=380, height=280, min_x=0, max_x=5, min_y=-560, max_y=560, baseline_x=0, baseline_y=0,
        horizontal_grid_lines=ft.ChartGridLines(interval=70, color=ft.Colors.GREY_300, width=1),
        vertical_grid_lines=ft.ChartGridLines(interval=1, color=ft.Colors.GREY_300, width=1),
        left_axis=ft.ChartAxis(title=ft.Text("Pa", size=12), labels=y_axis_labels, labels_size=45),
        bottom_axis=ft.ChartAxis(title=ft.Text("s", size=12), labels=x_axis_labels, labels_size=20),
    )

    # --- LAYOUT STRUTTURA ---
    controls_column = ft.Column([
        ft.Text("Pannello Datalogger HM-10", size=24, weight=ft.FontWeight.BOLD),
        ft.Row([scan_btn, device_dropdown]),
        ft.Row([connect_btn, disconnect_btn]),
        ft.Divider(),
        ft.Text("Controllo Misurazione", size=16, weight=ft.FontWeight.W_500),
        ft.Row([start_btn, stop_btn]),
        ft.Divider(),
        ft.Text("Comando Personalizzato", size=16, weight=ft.FontWeight.W_500),
        ft.Row([custom_input, ft.ElevatedButton("Invia", icon=ft.Icons.SEND, on_click=btn_send_custom)]),
        ft.Divider(),
        ft.Text("Console BLE", size=16, weight=ft.FontWeight.W_500),
        ft.Container(content=log_list, border=ft.border.all(1, ft.Colors.OUTLINE), border_radius=10, padding=10, height=180, width=520),
        status_text,
    ], width=520)

    visual_column = ft.Column([
        avg_pressure_box,
        ft.Container(content=pressure_chart, border=ft.border.all(1, ft.Colors.OUTLINE), border_radius=10, padding=10, width=430, height=330),
    ], width=430, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    page.add(
        ft.Row([controls_column, visual_column], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True)
    )

if __name__ == "__main__":
    ft.app(target=main)