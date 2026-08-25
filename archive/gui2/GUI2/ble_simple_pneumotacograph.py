import flet as ft
import asyncio
import csv
from datetime import datetime
from bleak import BleakScanner, BleakClient

# UUID standard del servizio Nordic UART
UART_RX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"

async def main(page: ft.Page):
    page.title = "ESP32 BLE Controller"
    page.window.width = 980
    page.window.height = 720
    page.theme_mode = ft.ThemeMode.LIGHT

    client_ble = [None]
    pressure_state = {
        "collecting": False,
        "sum": 0.0,
        "count": 0,
        "points": [],
        "avg": None,
        "reference_capacity": None,
        "resistance": None,
        "last_read_duration_ms": 0,
        "last_point_time_s": 0.0,
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

    def gui_log(msg, color=ft.Colors.BLACK):
        log_list.controls.append(ft.Text(msg, color=color))
        page.update()

    # --- GESTIONE DINAMICA ASSE X ---
    def extend_x_axis(x_val):
        current_max = pressure_chart.max_x if pressure_chart.max_x else 5.0
        if x_val >= current_max:
            new_max = current_max + 5.0
            pressure_chart.max_x = new_max
            
            step = 1
            if new_max > 20:
                step = 2
            if new_max > 50:
                step = 5
                
            new_x_labels = []
            for i in range(0, int(new_max) + 1, step):
                new_x_labels.append(
                    ft.ChartAxisLabel(i, label=ft.Text(str(i), size=11, color=ft.Colors.GREY_700))
                )
            
            pressure_chart.bottom_axis.labels = new_x_labels

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
            
            if msg == "STARTED":
                gui_log(f"🟢 [ESP32]: {msg}", ft.Colors.GREEN_700)
                pressure_state["collecting"] = True
                pressure_state["sum"] = 0.0
                pressure_state["count"] = 0
                pressure_state["points"] = []
                pressure_state["avg"] = None
                pressure_state["resistance"] = None
                
                avg_pressure_text.value = "Media Pressione Globale: -- Pa"
                resistance_text.value = "Resistenza: --"
                
                pressure_chart.data_series[0].data_points = []
                pressure_chart.max_x = 5.0
                base_x_labels = []
                for i in range(6):
                    base_x_labels.append(ft.ChartAxisLabel(i, label=ft.Text(str(i), size=11, color=ft.Colors.GREY_700)))
                pressure_chart.bottom_axis.labels = base_x_labels
                page.update()
                
            elif msg == "END":
                gui_log(f"🟢 [ESP32]: {msg}", ft.Colors.GREEN_700)
                if pressure_state["count"] > 0:
                    # Aggiornamento finale del grafico a fine lettura
                    pressure_chart.data_series[0].data_points = pressure_state["points"]
                    
                    avg = pressure_state["sum"] / pressure_state["count"]
                    pressure_state["avg"] = avg
                    avg_pressure_text.value = f"Media Globale: {avg:.2f} Pa"
                    update_resistance()
                    page.update()

                    # --- SEGMENTAZIONE DATI PER CSV ---
                    points = pressure_state["points"]
                    measurements = []
                    current_segment = []
                    
                    # 0=idle, 1=positiva, -1=negativa
                    phase = 0 
                    
                    for p in points:
                        y = p.y
                        current_segment.append(p)
                        
                        if phase == 0:
                            if y >= 0.3:
                                phase = 1
                            elif y <= -0.3:
                                phase = -1
                        elif phase == 1:
                            # TRIGGER: La curva scende da Positiva a Negativa. Inizia una nuova misura!
                            if y <= -0.3: 
                                current_segment.pop() # Rimuove il punto appena letto per inserirlo nel prossimo blocco
                                if current_segment:
                                    measurements.append(current_segment)
                                current_segment = [p] # Inizia il nuovo blocco
                                phase = -1
                        elif phase == -1:
                            # Se passa a positiva, continua semplicemente nella stessa "misurazione"
                            if y >= 0.3:
                                phase = 1

                    if current_segment:
                        measurements.append(current_segment)

                    # --- ESPORTAZIONE CSV A RIGHE (CON FILTRO ZONA MORTA) ---
                    if measurements:
                        filename = f"misure_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        cap_rif = pressure_state["reference_capacity"]
                        str_cap_rif = f"{cap_rif}" if cap_rif is not None else "--"
                        
                        try:
                            with open(filename, mode='w', newline='') as f:
                                writer = csv.writer(f)
                                writer.writerow(["Misura N.", "Pressione Media (Pa)", "Litri di Riferimento", "Istante Inizio (s)", "Durata Attiva (s)"])
                                
                                misura_effettiva_idx = 1
                                for seg in measurements:
                                    # FILTRO: Mantieni solo i punti FUORI dalla zona morta
                                    punti_attivi = [p for p in seg if p.y >= 0.3 or p.y <= -0.3]
                                    
                                    # Se il segmento ha punti validi dopo il filtro
                                    if len(punti_attivi) > 0:
                                        t_inizio = punti_attivi[0].x
                                        t_fine = punti_attivi[-1].x
                                        t_misura = t_fine - t_inizio
                                        
                                        if t_misura <= 0:
                                            t_misura = 0.02
                                        
                                        somma_p = sum(p.y for p in punti_attivi)
                                        p_media = somma_p / len(punti_attivi)
                                        
                                        writer.writerow([
                                            misura_effettiva_idx, 
                                            f"{p_media:.2f}", 
                                            str_cap_rif, 
                                            f"{t_inizio:.3f}",
                                            f"{t_misura:.3f}"
                                        ])
                                        misura_effettiva_idx += 1
                                        
                            gui_log(f"💾 Salvate {misura_effettiva_idx - 1} misure in: {filename}", ft.Colors.GREEN)
                        except Exception as e:
                            gui_log(f"❌ Errore salvataggio CSV: {e}", ft.Colors.RED)
                    else:
                        gui_log("⚠️ CSV non generato: nessun dato oltre la soglia minima (+/- 0.3 Pa).", ft.Colors.ORANGE)

                else:
                    avg_pressure_text.value = "Media Pressione: -- Pa"
                    resistance_text.value = "Resistenza: --"
                
                pressure_state["collecting"] = False
                page.update()
                
            elif pressure_state["collecting"] and msg.startswith("P "):
                parts = msg.split()
                if len(parts) >= 4 and parts[0] == "P" and parts[2] == "Pa":
                    try:
                        pressure = float(parts[1])
                        time_ms = None
                        if len(parts) >= 5 and parts[4] == "ms":
                            try:
                                time_ms = float(parts[3])
                            except ValueError:
                                time_ms = None
                        if time_ms is None:
                            time_ms = len(pressure_state["points"]) * 20
                        
                        x = time_ms / 1000.0
                        
                        pressure_state["last_point_time_s"] = x
                        pressure_state["last_read_duration_ms"] = time_ms
                        pressure_state["sum"] += pressure
                        pressure_state["count"] += 1
                        
                        # Fix Performance: Aggiunto punto SENZA tooltip
                        pressure_state["points"].append(
                            ft.LineChartDataPoint(x=x, y=pressure) 
                        )
                        
                        # Fix Performance: Aggiorna la GUI solo una volta ogni 20 punti (circa ogni 400ms)
                        if pressure_state["count"] % 20 == 0:
                            pressure_chart.data_series[0].data_points = pressure_state["points"]
                            extend_x_axis(x)
                            avg = pressure_state["sum"] / pressure_state["count"]
                            pressure_state["avg"] = avg
                            avg_pressure_text.value = f"Media Pressione: {avg:.2f} Pa"
                            page.update()
                            
                    except ValueError:
                        pass
        except Exception:
            pass

    async def connect_click(e):
        if not device_dropdown.value:
            gui_log("⚠️ Seleziona un dispositivo!", ft.Colors.ORANGE)
            return
        gui_log(f"🔌 Connessione a {device_dropdown.value}...")
        client_ble[0] = BleakClient(device_dropdown.value)
        try:
            await client_ble[0].connect()
            try:
                await client_ble[0].write_gatt_char(UART_TX_CHAR_UUID, "\r\n".encode('utf-8'), response=True)
                gui_log("🔵 Inviato handshake iniziale", ft.Colors.BLUE)
            except Exception as ex:
                gui_log(f"⚠️ Handshake iniziale fallito: {ex}", ft.Colors.ORANGE)
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

    # --- SEND CMD ---
    async def send_cmd(cmd):
        cmd = cmd.strip().lstrip('.').strip()
        if cmd == "":
            return
        cmd_to_send = cmd + "\r\n"
        if client_ble[0] and client_ble[0].is_connected:
            try:
                await client_ble[0].write_gatt_char(UART_TX_CHAR_UUID, cmd_to_send.encode('utf-8'), response=True)
                gui_log(f"🔵 [INVIATO]: {cmd}", ft.Colors.BLUE_700)
            except Exception as ex:
                gui_log(f"❌ Errore invio: {ex}", ft.Colors.RED)
        else:
            gui_log("⚠️ Non connesso!", ft.Colors.ORANGE)

    # --- BOTTONI E UI ---
    scan_btn = ft.ElevatedButton("1. Scansiona", icon=ft.Icons.SEARCH, on_click=scan_click)
    connect_btn = ft.ElevatedButton("2. Connetti", icon=ft.Icons.BLUETOOTH, on_click=connect_click)
    disconnect_btn = ft.ElevatedButton("Disconnetti", icon=ft.Icons.BLUETOOTH_DISABLED, on_click=disconnect_click, disabled=True)

    async def btn_send_custom(e):
        cmd = custom_input.value.strip().lstrip('.').strip()
        if cmd != "":
            await send_cmd(cmd)
            custom_input.value = ""
            page.update()

    def update_read_preview(e=None):
        raw = read_ms_input.value.strip()
        if raw == "":
            read_count_text.value = "Letture: 0"
            page.update()
            return
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits != raw:
            read_ms_input.value = digits
            raw = digits
        if digits == "":
            read_count_text.value = "Letture: 0"
        else:
            ms = int(digits)
            rounded_ms = round(ms / 20) * 20
            if rounded_ms < 0:
                rounded_ms = 0
            read_count_text.value = f"Letture: {rounded_ms // 20}"
        page.update()

    def update_reference_capacity(e=None):
        raw = capacity_input.value.strip()
        if raw == "":
            pressure_state["reference_capacity"] = None
            capacity_info_text.value = "Capacità di riferimento: -- L"
        else:
            safe = "".join(ch for ch in raw if ch.isdigit() or ch == '.')
            if safe.count('.') > 1:
                parts = safe.split('.')
                safe = parts[0] + '.' + ''.join(parts[1:])
            capacity_input.value = safe
            try:
                val = float(safe)
                if val > 0:
                    pressure_state["reference_capacity"] = val
                    capacity_info_text.value = f"Capacità di riferimento: {val:.2f} L"
                else:
                    pressure_state["reference_capacity"] = None
                    capacity_info_text.value = "Capacità di riferimento: -- L"
            except ValueError:
                pressure_state["reference_capacity"] = None
                capacity_info_text.value = "Capacità di riferimento: -- L"
        update_resistance()

    def update_resistance():
        if (pressure_state["avg"] is None
                or pressure_state["reference_capacity"] is None
                or pressure_state["last_read_duration_ms"] <= 0):
            resistance_text.value = "Resistenza: --"
        else:
            time_s = pressure_state["last_read_duration_ms"] / 1000.0
            resistance = pressure_state["avg"] * time_s / pressure_state["reference_capacity"]
            pressure_state["resistance"] = resistance
            resistance_text.value = f"Resistenza: {resistance:.3f}"
        page.update()

    async def btn_send_read(e):
        raw = read_ms_input.value.strip()
        if not raw.isdigit() or int(raw) <= 0:
            gui_log("⚠️ Inserisci un valore valido in ms", ft.Colors.ORANGE)
            return
        ms = int(raw)
        rounded_ms = round(ms / 20) * 20
        if rounded_ms <= 0:
            gui_log("⚠️ Inserisci almeno 35 ms per ottenere una lettura", ft.Colors.ORANGE)
            return
        reads = rounded_ms // 20
        read_ms_input.value = str(rounded_ms)
        pressure_state["last_read_duration_ms"] = rounded_ms
        page.update()
        await send_cmd(f"READ {reads}")

    custom_input = ft.TextField(label="Scrivi un comando...", expand=True, on_submit=btn_send_custom)
    custom_cmd_row = ft.Row([
        custom_input,
        ft.ElevatedButton("Invia", icon=ft.Icons.SEND, on_click=btn_send_custom)
    ])

    read_ms_input = ft.TextField(
        label="ms totali",
        width=140,
        value="70",
        on_change=update_read_preview,
        on_submit=btn_send_read,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    read_count_text = ft.Text("Letture: 1", size=14)

    capacity_input = ft.TextField(
        label="Capacità riferimento (L)",
        width=180,
        value="",
        on_change=update_reference_capacity,
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    capacity_info_text = ft.Text("Capacità di riferimento: -- L", size=14)
    resistance_text = ft.Text("Resistenza: --", size=14)
    resistance_box = ft.Container(
        content=ft.Column([capacity_info_text, resistance_text], tight=True),
        border=ft.border.all(1, ft.Colors.GREEN_700),
        border_radius=10,
        padding=10,
        width=260,
    )

    y_axis_labels = []
    for val in range(-560, 561, 140):
        y_axis_labels.append(ft.ChartAxisLabel(val, label=ft.Text(str(val), size=11, color=ft.Colors.GREY_700)))

    x_axis_labels = []
    for i in range(6):
        x_axis_labels.append(ft.ChartAxisLabel(i, label=ft.Text(str(i), size=11, color=ft.Colors.GREY_700)))

    # --- GRAFICO ---
    pressure_chart = ft.LineChart(
        data_series=[
            ft.LineChartData(
                data_points=[],
                color=ft.Colors.BLUE,
                curved=True,
                stroke_width=2,
                point=False,
            )
        ],
        width=380,
        height=280,
        min_x=0,
        max_x=5,
        min_y=-560,
        max_y=560,
        baseline_x=0,
        baseline_y=0,
        horizontal_grid_lines=ft.ChartGridLines(interval=70, color=ft.Colors.GREY_300, width=1),
        vertical_grid_lines=ft.ChartGridLines(interval=1, color=ft.Colors.GREY_300, width=1),
        left_axis=ft.ChartAxis(
            title=ft.Text("Pa", size=12, color=ft.Colors.GREY_700),
            title_size=30,
            show_labels=True,
            labels_size=45,
            labels=y_axis_labels,
        ),
        bottom_axis=ft.ChartAxis(
            title=ft.Text("s", size=12, color=ft.Colors.GREY_700),
            title_size=30,
            show_labels=True,
            labels_size=20,
            labels=x_axis_labels,
        ),
    )

    read_row = ft.Row([
        ft.Text("READ", size=18, weight=ft.FontWeight.BOLD),
        read_ms_input,
        ft.ElevatedButton("Invia READ", icon=ft.Icons.SEND, on_click=btn_send_read),
        read_count_text,
    ], alignment=ft.MainAxisAlignment.START, spacing=15)

    log_container = ft.Container(
        content=log_list,
        border=ft.border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
        padding=10,
        height=150,
        width=520,
    )

    chart_box = ft.Container(
        content=pressure_chart,
        border=ft.border.all(1, ft.Colors.OUTLINE),
        border_radius=10,
        padding=10,
        width=430,
        height=330,
    )

    controls_column = ft.Column([
        ft.Text("Pannello di Controllo ESP32", size=24, weight=ft.FontWeight.BOLD),
        ft.Row([scan_btn, device_dropdown]),
        ft.Row([connect_btn, disconnect_btn]),
        ft.Divider(),
        ft.Row([
            capacity_input,
            resistance_box,
        ], alignment=ft.MainAxisAlignment.START, spacing=20),
        read_row,
        ft.Divider(),
        ft.Text("Comando Personalizzato", size=16, weight=ft.FontWeight.W_500),
        custom_cmd_row,
        ft.Divider(),
        ft.Text("Console BLE", size=16, weight=ft.FontWeight.W_500),
        log_container,
        status_text,
    ], width=520)

    visual_column = ft.Column([
        avg_pressure_box,
        chart_box,
    ], width=430, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    page.add(
        ft.Row([
            controls_column,
            visual_column,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, expand=True),
    )

if __name__ == "__main__":
    ft.app(target=main)