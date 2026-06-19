import flet as ft
import asyncio
import csv
from datetime import datetime
from bleak import BleakScanner, BleakClient
from collections import deque
import os
import queue
import threading
import time

# UUID standard per la comunicazione seriale dell'HM-10
HM10_UART_CHAR_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"
UART_RX_CHAR_UUID = HM10_UART_CHAR_UUID
UART_TX_CHAR_UUID = HM10_UART_CHAR_UUID

class BLEDevice:
    def __init__(self, name, address):
        self.name = name
        self.address = address
    
    def __repr__(self):
        return f"{self.name} ({self.address})"

class HM10BLEController:
    """Controller for HM-10 BLE communication and data handling"""
    def __init__(self, callback):
        self.client = None
        self.callback = callback
        self.is_connected = False
        self.data_buffer = deque(maxlen=100)
        self.csv_file = None
        self.csv_writer = None
        self.recording = False
        
    async def scan_devices(self):
        """Scan for available BLE devices"""
        scanner = BleakScanner()
        devices = await scanner.discover()
        result = []
        for device in devices:
            result.append(BLEDevice(device.name or "Unknown", device.address))
        return result
    
    async def connect(self, device_address):
        """Connect to a specific BLE device"""
        try:
            self.client = BleakClient(device_address)
            await self.client.connect()
            # Start listening for notifications
            await self.client.start_notify(UART_RX_CHAR_UUID, self._notification_handler)
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def _notification_handler(self, sender, data):
        """Handle incoming BLE notifications"""
        try:
            message = data.decode('utf-8').strip()
            self.data_buffer.append(message)
            self.callback(message)
        except Exception as e:
            print(f"Decoding error: {e}")
    
    async def send_command(self, command):
        """Send command to HM-10"""
        if self.client and self.is_connected:
            try:
                await self.client.write_gatt_char(UART_TX_CHAR_UUID, command.encode())
                return True
            except Exception as e:
                print(f"Send error: {e}")
                return False
        return False
    
    async def disconnect(self):
        """Disconnect from BLE device"""
        if self.client:
            try:
                await self.client.stop_notify(UART_RX_CHAR_UUID)
                await self.client.disconnect()
            except:
                pass
        self.is_connected = False
        self.stop_recording()
    
    def start_recording(self, filename):
        """Start recording sensor data to CSV"""
        self.csv_file = open(filename, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['Flow (L/s)', 'Position (ticks)', 'PWM DC (%)', 'Time (ms)'])
        self.recording = True
    
    def stop_recording(self):
        """Stop recording sensor data"""
        if self.csv_file:
            self.csv_file.close()
        self.recording = False
    
    def log_sensor_data(self, flow, position, pwm, time_ms=None):
        """Log sensor data to CSV if recording"""
        if self.recording and self.csv_writer:
            if time_ms is not None:
                self.csv_writer.writerow([flow, position, pwm, time_ms])
            else:
                self.csv_writer.writerow([flow, position, pwm, ''])
            self.csv_file.flush()

def main(page: ft.Page):
    page.title = "HM-10 BLE Control Panel"
    page.window.width = 1200
    page.window.height = 900
    page.bgcolor = "#FFFFFF"
    page.theme_mode = "light"
    
    # State management
    state = {
        'ble': None,
        'devices': [],
        'selected_device': None,
        'connected': False,
        'mode': 'debug',
        'flow_data': deque(maxlen=50),
        'position_data': deque(maxlen=50),
        'pwm_data': deque(maxlen=50),
        'time_data': deque(maxlen=50),
        'calibration_active': False,
        'message_queue': queue.Queue(),  # Thread-safe message queue
    }
    
    # ============ BLE Callback ============
    def on_ble_data(message):
        """Callback when data is received from HM-10 (runs on BLE thread)"""
        print(f"Received: {message}")
        # Queue the message for safe processing on main thread
        state['message_queue'].put(message)
    
    def process_message_queue():
        """Process queued BLE messages on the main thread"""
        try:
            while True:
                try:
                    message = state['message_queue'].get_nowait()
                    
                    # Update debug terminal
                    if state['mode'] == 'debug':
                        debug_output.value += f"\n← {message}"
                    
                    # Parse sensor data
                    if message.startswith("SNSR"):
                        parts = message.split()
                        if len(parts) >= 4:
                            try:
                                flow = float(parts[1])
                                position = float(parts[2])
                                pwm = float(parts[3])
                                time_ms = float(parts[4]) if len(parts) > 4 else None
                                
                                # Handle calibration mode
                                if state['calibration_active']:
                                    if time_ms == -1:
                                        # Start calibration - clear data and create CSV
                                        state['flow_data'].clear()
                                        state['position_data'].clear()
                                        state['pwm_data'].clear()
                                        state['time_data'].clear()
                                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        csv_file = f"calibration_data_{timestamp}.csv"
                                        state['ble'].start_recording(csv_file)
                                        status_text.value = f"📊 Calibration started, recording to {csv_file}"
                                    elif time_ms == -2:
                                        # Stop calibration
                                        state['ble'].stop_recording()
                                        state['calibration_active'] = False
                                        status_text.value = "✓ Calibration completed"
                                
                                # Update data buffers
                                state['flow_data'].append(flow)
                                state['position_data'].append(position)
                                state['pwm_data'].append(pwm)
                                if time_ms is not None:
                                    state['time_data'].append(time_ms)
                                
                                # Log to CSV if recording
                                if state['ble'] and state['ble'].recording:
                                    state['ble'].log_sensor_data(flow, position, pwm, time_ms)
                                
                                # Update charts
                                update_charts()
                            except Exception as e:
                                print(f"Parse error: {e}")
                    
                    page.update()
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Queue processing error: {e}")
    
    # ============ Chart Update Function ============
    def update_charts():
        """Update all three charts with current data"""
        # Flow chart
        flow_chart.data_series = [
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(i, flow) 
                    for i, flow in enumerate(state['flow_data'])
                ],
                stroke_width=2,
                color="#1976D2",
                curved=True,
            )
        ]
        
        # Position chart
        position_chart.data_series = [
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(i, pos) 
                    for i, pos in enumerate(state['position_data'])
                ],
                stroke_width=2,
                color="#388E3C",
                curved=True,
            )
        ]
        
        # PWM chart
        pwm_chart.data_series = [
            ft.LineChartData(
                data_points=[
                    ft.LineChartDataPoint(i, pwm) 
                    for i, pwm in enumerate(state['pwm_data'])
                ],
                stroke_width=2,
                color="#F57C00",
                curved=True,
            )
        ]
    
    # ============ BLE Scanning ============
    async def scan_ble_devices():
        """Scan and populate device dropdown"""
        scan_btn.disabled = True
        scan_btn.label = "Scanning..."
        page.update()
        
        try:
            state['ble'] = HM10BLEController(on_ble_data)
            devices = await state['ble'].scan_devices()
            state['devices'] = devices
            
            device_options = [
                ft.dropdown.Option(
                    device.address,
                    text=device.name if device.name and device.name != "Unknown" else device.address
                )
                for device in devices
            ]
            device_dropdown.options = device_options
            device_dropdown.disabled = False
            
            # Auto-select DSD devices
            dsd_found = False
            for device in devices:
                if device.name and device.name.startswith("DSD"):
                    device_dropdown.value = device.address
                    connect_btn.disabled = False  # Manually enable connect button
                    status_text.value = f"🎏 Auto-selected: {device.name}"
                    dsd_found = True
                    break
            
            if not dsd_found:
                connect_btn.disabled = True  # Disable if no device selected
            
            if device_options:
                status_text.value = f"✓ Found {len(devices)} device(s)"
            else:
                status_text.value = "✗ No devices found"
            
            page.update()
        except Exception as e:
            status_text.value = f"✗ Scan error: {e}"
            page.update()
        finally:
            scan_btn.disabled = False
            scan_btn.label = "Refresh Devices"
            page.update()
    
    # ============ BLE Connection ============
    async def connect_to_device():
        """Connect to selected BLE device"""
        if not device_dropdown.value:
            status_text.value = "✗ Please select a device"
            page.update()
            return
        
        connect_btn.disabled = True
        connect_btn.label = "Connecting..."
        page.update()
        
        try:
            if await state['ble'].connect(device_dropdown.value):
                state['connected'] = True
                status_text.value = "✓ Connected!"
                connect_btn.label = "Disconnect"
                connect_btn.on_click = disconnect_device
                device_dropdown.disabled = True
                scan_btn.disabled = True
                mode_selector.disabled = False
            else:
                status_text.value = "✗ Connection failed"
            page.update()
        except Exception as e:
            status_text.value = f"✗ Error: {e}"
            page.update()
        finally:
            connect_btn.disabled = False
            page.update()
    
    def disconnect_device(e):
        """Disconnect from BLE device"""
        if state['ble']:
            asyncio.run(state['ble'].disconnect())
        state['connected'] = False
        status_text.value = "Disconnected"
        connect_btn.label = "Connect"
        connect_btn.on_click = lambda _: asyncio.run(connect_to_device())
        device_dropdown.disabled = False
        scan_btn.disabled = False
        mode_selector.disabled = True
        page.update()
    
    # ============ Mode Switching ============
    def on_mode_change(e):
        """Handle mode selection change"""
        state['mode'] = mode_selector.value
        update_mode_view()
    
    def update_mode_view():
        """Update UI based on selected mode"""
        # Hide all mode panels
        debug_panel.visible = False
        linear_flow_panel.visible = False
        sinusoidal_panel.visible = False
        calibration_panel.visible = False
        
        # Show selected mode panel
        if state['mode'] == 'debug':
            debug_panel.visible = True
        elif state['mode'] == 'linear':
            linear_flow_panel.visible = True
        elif state['mode'] == 'sinusoidal':
            sinusoidal_panel.visible = True
        elif state['mode'] == 'calibration':
            calibration_panel.visible = True
        
        page.update()
    
    # ============ Debug Mode ============
    async def send_debug_command(e):
        """Send debug command to HM-10"""
        command = debug_input.value.strip()
        if not command:
            return
        
        debug_output.value += f"\n→ {command}"
        
        if await state['ble'].send_command(command):
            debug_input.value = ""
        else:
            debug_output.value += "\n✗ Send failed"
        
        page.update()
    
    # ============ Linear Flow Mode ============
    async def start_linear_flow(e):
        """Start linear flow mode"""
        try:
            flow = float(linear_flow_input.value)
            command = f"Mode 0 {flow}"
            if await state['ble'].send_command(command):
                status_text.value = f"📈 Linear Flow started: {flow} L/s"
            else:
                status_text.value = "✗ Failed to start"
            page.update()
        except ValueError:
            status_text.value = "✗ Invalid flow value"
            page.update()
    
    # ============ Sinusoidal Mode ============
    async def start_sinusoidal(e):
        """Start sinusoidal mode"""
        try:
            amplitude = float(sinusoidal_amplitude_input.value)
            frequency = float(sinusoidal_frequency_input.value)
            command = f"Mode 1 {amplitude} {frequency}"
            if await state['ble'].send_command(command):
                status_text.value = f"〰️ Sinusoidal started: {amplitude} L/s @ {frequency} Hz"
            else:
                status_text.value = "✗ Failed to start"
            page.update()
        except ValueError:
            status_text.value = "✗ Invalid amplitude or frequency"
            page.update()
    
    # ============ Calibration Mode ============
    async def start_calibration(e):
        """Start calibration mode"""
        try:
            start_flow = float(calibration_start_input.value)
            end_flow = float(calibration_end_input.value)
            steps = int(calibration_steps_input.value)
            command = f"Mode 2 {start_flow} {end_flow} {steps}"
            if await state['ble'].send_command(command):
                state['calibration_active'] = True
                status_text.value = f"⚙️ Calibration started: {start_flow}-{end_flow} L/s in {steps} steps"
            else:
                status_text.value = "✗ Failed to start calibration"
            page.update()
        except ValueError:
            status_text.value = "✗ Invalid calibration parameters"
            page.update()
    
    # ============ Create Charts ============
    def create_chart(title, y_label):
        """Create a line chart"""
        chart = ft.LineChart(
            data_series=[
                ft.LineChartData(
                    data_points=[],
                    stroke_width=2,
                    color="#1976D2",
                    curved=True,
                )
            ],
            border=ft.border.all(1, "#CCCCCC"),
            left_axis=ft.ChartAxis(
                labels_size=40,
                title=ft.Text(y_label, size=12, color="#000000"),
            ),
            bottom_axis=ft.ChartAxis(
                labels_size=30,
            ),
            min_y=0,
            max_y=100,
            expand=True,
            interactive=False,
        )
        
        container = ft.Column(
            controls=[
                ft.Text(title, size=14, weight="bold", color="#000000"),
                chart,
            ],
            expand=True,
        )
        return container, chart
    
    # Create chart containers
    flow_container, flow_chart = create_chart("Flow (L/s)", "L/s")
    position_container, position_chart = create_chart("Motor Position (ticks)", "Ticks")
    pwm_container, pwm_chart = create_chart("PWM Duty Cycle (%)", "%")
    
    # ============ Build UI Components ============
    
    # Status and Connection Section
    status_text = ft.Text("Ready", size=12, color="#000000")
    
    device_dropdown = ft.Dropdown(
        label="Select Device",
        width=300,
        disabled=False,
        label_style=ft.TextStyle(color="#000000"),
        on_change=lambda e: setattr(connect_btn, 'disabled', not device_dropdown.value) or page.update(),
    )
    
    scan_btn = ft.IconButton(
        icon="refresh",
        tooltip="Scan for devices",
        on_click=lambda _: asyncio.run(scan_ble_devices()),
    )
    
    connect_btn = ft.ElevatedButton(
        "Connect",
        on_click=lambda _: asyncio.run(connect_to_device()),
        disabled=True,
    )
    
    connection_row = ft.Row(
        controls=[
            device_dropdown,
            scan_btn,
            connect_btn,
        ],
        alignment=ft.MainAxisAlignment.START,
        spacing=10,
    )
    
    # Mode Selector
    mode_selector = ft.Dropdown(
        label="Select Mode",
        width=250,
        options=[
            ft.dropdown.Option("debug", text="Debug Terminal"),
            ft.dropdown.Option("linear", text="Linear Flow"),
            ft.dropdown.Option("sinusoidal", text="Sinusoidal"),
            ft.dropdown.Option("calibration", text="Calibration"),
        ],
        value="debug",
        on_change=on_mode_change,
        disabled=True,
        label_style=ft.TextStyle(color="#000000"),
    )
    
    # ============ DEBUG MODE ============
    debug_output = ft.TextField(
        multiline=True,
        read_only=True,
        min_lines=10,
        max_lines=10,
        expand=True,
        text_style=ft.TextStyle(color="#000000", size=12),
    )
    
    debug_input = ft.TextField(
        label="Enter command",
        on_submit=lambda _: asyncio.run(send_debug_command(None)),
        expand=True,
        text_style=ft.TextStyle(color="#000000"),
    )
    
    debug_send_btn = ft.IconButton(
        icon="send",
        on_click=lambda _: asyncio.run(send_debug_command(None)),
    )
    
    debug_panel = ft.Column(
        controls=[
            ft.Text("Debug Terminal", size=14, weight="bold", color="#000000"),
            debug_output,
            ft.Row(
                controls=[debug_input, debug_send_btn],
                expand=True,
            ),
        ],
        expand=True,
        visible=True,
    )
    
    # ============ LINEAR FLOW MODE ============
    linear_flow_input = ft.TextField(
        label="Flow (L/s)",
        width=200,
        value="1.0",
        text_style=ft.TextStyle(color="#000000"),
    )
    
    linear_flow_btn = ft.ElevatedButton(
        "Start",
        on_click=lambda _: asyncio.run(start_linear_flow(None)),
    )
    
    linear_flow_panel = ft.Column(
        controls=[
            ft.Text("Linear Flow Mode", size=14, weight="bold", color="#000000"),
            ft.Row(
                controls=[linear_flow_input, linear_flow_btn],
                spacing=10,
            ),
        ],
        visible=False,
    )
    
    # ============ SINUSOIDAL MODE ============
    sinusoidal_amplitude_input = ft.TextField(
        label="Peak Flow (L/s)",
        width=200,
        value="2.0",
        text_style=ft.TextStyle(color="#000000"),
    )
    
    sinusoidal_frequency_input = ft.TextField(
        label="Frequency (Hz)",
        width=200,
        value="1.0",
        text_style=ft.TextStyle(color="#000000"),
    )
    
    sinusoidal_btn = ft.ElevatedButton(
        "Start",
        on_click=lambda _: asyncio.run(start_sinusoidal(None)),
    )
    
    sinusoidal_panel = ft.Column(
        controls=[
            ft.Text("Sinusoidal Mode", size=14, weight="bold", color="#000000"),
            ft.Row(
                controls=[sinusoidal_amplitude_input, sinusoidal_frequency_input],
                spacing=10,
            ),
            ft.Row(
                controls=[sinusoidal_btn],
                spacing=10,
            ),
        ],
        visible=False,
    )
    
    # ============ CALIBRATION MODE ============
    calibration_start_input = ft.TextField(
        label="Start Flow (L/s)",
        width=200,
        value="0.5",
        text_style=ft.TextStyle(color="#000000"),
    )
    
    calibration_end_input = ft.TextField(
        label="End Flow (L/s)",
        width=200,
        value="5.0",
        text_style=ft.TextStyle(color="#000000"),
    )
    
    calibration_steps_input = ft.TextField(
        label="Steps",
        width=200,
        value="10",
        text_style=ft.TextStyle(color="#000000"),
    )
    
    calibration_btn = ft.ElevatedButton(
        "Start Calibration",
        on_click=lambda _: asyncio.run(start_calibration(None)),
    )
    
    calibration_panel = ft.Column(
        controls=[
            ft.Text("Calibration Mode", size=14, weight="bold", color="#000000"),
            ft.Row(
                controls=[
                    calibration_start_input,
                    calibration_end_input,
                    calibration_steps_input,
                ],
                spacing=10,
            ),
            ft.Row(
                controls=[calibration_btn],
                spacing=10,
            ),
        ],
        visible=False,
    )
    
    # ============ Mode Controls ============
    mode_controls = ft.Column(
        controls=[
            debug_panel,
            linear_flow_panel,
            sinusoidal_panel,
            calibration_panel,
        ],
        expand=True,
    )
    
    # ============ Charts Section ============
    charts_row = ft.Row(
        controls=[
            ft.Container(
                content=flow_container,
                expand=True,
                border=ft.border.all(1, "#CCCCCC"),
                bgcolor="#FFFFFF",
            ),
            ft.Container(
                content=position_container,
                expand=True,
                border=ft.border.all(1, "#CCCCCC"),
                bgcolor="#FFFFFF",
            ),
            ft.Container(
                content=pwm_container,
                expand=True,
                border=ft.border.all(1, "#CCCCCC"),
                bgcolor="#FFFFFF",
            ),
        ],
        expand=True,
        spacing=10,
    )
    
    # ============ Main Layout ============
    main_column = ft.Column(
        controls=[
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("HM-10 BLE Control Panel", size=20, weight="bold", color="#000000"),
                        status_text,
                        connection_row,
                    ],
                    spacing=10,
                ),
                padding=15,
                bgcolor="#FFFFFF",
                border=ft.border.all(1, "#CCCCCC"),
            ),
            ft.Row(
                controls=[
                    ft.Text("Operation Mode:", weight="bold", color="#000000"),
                    mode_selector,
                ],
                spacing=10,
            ),
            ft.Container(
                content=mode_controls,
                expand=True,
            ),
            charts_row,
        ],
        expand=True,
        spacing=5,
    )
    
    # Start message queue processor as background task
    def message_queue_worker():
        """Placeholder for queue processing - actual processing done in background thread"""
        pass
    
    # Set up periodic message processing using background thread
    def setup_message_processor():
        """Setup periodic message processing"""
        def worker():
            while True:
                try:
                    process_message_queue()
                except Exception as e:
                    print(f"Message worker error: {e}")
                time.sleep(0.05)
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    page.add(main_column)
    
    # Setup background message processing
    setup_message_processor()
    
    # Initial scan on startup
    asyncio.run(scan_ble_devices())

if __name__ == "__main__":
    ft.app(target=main)