import sys
import asyncio
import time
import csv
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QGroupBox, QTabWidget,
    QLineEdit, QTextEdit, QMessageBox, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer
import pyqtgraph as pg
from bleak import BleakClient, BleakScanner
import qasync
from qasync import asyncSlot

# UUIDs
HM10_UART_CHAR_UUID = "0000FFE1-0000-1000-8000-00805F9B34FB"
UART_RX_CHAR_UUID = HM10_UART_CHAR_UUID
UART_TX_CHAR_UUID = HM10_UART_CHAR_UUID

class HM10App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HM-10 BLE Controller & Monitor")
        self.resize(1200, 800)

        # BLE State
        self.client = None
        self.rx_buffer = b""
        self.devices_dict = {}

        # Logging & Mode State
        self.is_logging = False
        self.is_calibrating = False
        self.csv_file = None
        self.csv_writer = None

        # Message Rate Tracking
        self.msg_counter = 0

        # Parameters
        self.current_resistance = 1.0  # Default multiplier

        # Dynamic Plot Data Buffers
        self.start_time = time.time()
        self.t_data = []
        self.flow_data = []
        self.pos_data = []
        self.pwm_data = []

        self.setup_ui()

        # Timer for updating messages per second (MPS)
        self.mps_timer = QTimer()
        self.mps_timer.timeout.connect(self.update_mps)
        self.mps_timer.start(1000)  # Trigger every 1000 ms (1 second)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        # Left gets ~62% of the screen, Right gets ~38%
        main_layout.addLayout(left_layout, stretch=5)
        main_layout.addLayout(right_layout, stretch=3)

        # =========================================================
        # LEFT SIDE: PyQtGraph Plots & MPS Label
        # =========================================================
        plot_group = QGroupBox("Real-time Data")
        plot_layout = QVBoxLayout(plot_group)
        pg.setConfigOptions(antialias=True)

        self.plot_flow = pg.PlotWidget(title="Flow (L/s)")
        self.plot_flow.showGrid(x=True, y=True)
        self.line_flow = self.plot_flow.plot(pen=pg.mkPen('b', width=2))
        
        self.plot_pos = pg.PlotWidget(title="Motor Position (ticks)")
        self.plot_pos.showGrid(x=True, y=True)
        self.line_pos = self.plot_pos.plot(pen=pg.mkPen('g', width=2))

        self.plot_pwm = pg.PlotWidget(title="PWM Duty Cycle (%)")
        self.plot_pwm.showGrid(x=True, y=True)
        self.line_pwm = self.plot_pwm.plot(pen=pg.mkPen('r', width=2))

        plot_layout.addWidget(self.plot_flow)
        plot_layout.addWidget(self.plot_pos)
        plot_layout.addWidget(self.plot_pwm)

        left_layout.addWidget(plot_group)

        # MPS Label (Bottom Left, Small, Dark Gray)
        self.lbl_mps = QLabel("0 msg/s")
        self.lbl_mps.setStyleSheet("color: darkgray; font-size: 10px;")
        left_layout.addWidget(self.lbl_mps, alignment=Qt.AlignmentFlag.AlignLeft)

        # =========================================================
        # RIGHT SIDE: Controls & Terminals
        # =========================================================
        
        # 1. Connection
        conn_group = QGroupBox("BLE Connection")
        conn_layout = QVBoxLayout(conn_group)

        self.btn_scan = QPushButton("Scan/Refresh")
        self.btn_scan.clicked.connect(self.start_scan)
        
        self.combo_devices = QComboBox()

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.connect_device)

        self.btn_disconnect = QPushButton("Force Disconnect")
        self.btn_disconnect.setEnabled(False)
        self.btn_disconnect.clicked.connect(self.disconnect_device)

        self.lbl_status = QLabel("Status: Disconnected")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")

        conn_layout.addWidget(self.btn_scan)
        conn_layout.addWidget(self.combo_devices)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_connect)
        btn_layout.addWidget(self.btn_disconnect)
        conn_layout.addLayout(btn_layout)
        
        conn_layout.addWidget(self.lbl_status)

        right_layout.addWidget(conn_group)

        # 2. Global Commands
        global_group = QGroupBox("Global Commands")
        global_layout = QHBoxLayout(global_group)

        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; font-size: 14px;")
        self.btn_stop.setMinimumHeight(40)
        self.btn_stop.clicked.connect(self.send_stop)

        self.btn_self_test = QPushButton("Self Test")
        self.btn_self_test.setMinimumHeight(40)
        self.btn_self_test.clicked.connect(self.send_self_test)

        global_layout.addWidget(self.btn_stop)
        global_layout.addWidget(self.btn_self_test)

        right_layout.addWidget(global_group)

        # 2.5 General Parameters
        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)
        
        res_layout = QHBoxLayout()
        self.ent_resistance = QLineEdit("1.0")
        btn_set_res = QPushButton("Set")
        btn_set_res.clicked.connect(self.send_resistance)
        res_layout.addWidget(self.ent_resistance)
        res_layout.addWidget(btn_set_res)

        self.ent_ref_volume = QLineEdit()
        
        params_layout.addRow("Resistance (Pa/L/s):", res_layout)
        params_layout.addRow("Ref Volume (L):", self.ent_ref_volume)
        
        right_layout.addWidget(params_group)

        # 3. Modes (Tabs)
        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True) 
        
        self.setup_mode_1_debug()
        self.setup_mode_2_linear()
        self.setup_mode_3_sinusoidal()
        self.setup_mode_4_calibration()
        self.setup_mode_5_push()
        self.setup_mode_6_home()
        right_layout.addWidget(self.tabs)

    def setup_mode_1_debug(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        self.txt_debug = QTextEdit()
        self.txt_debug.setReadOnly(True)
        
        input_layout = QHBoxLayout()
        self.ent_debug = QLineEdit()
        self.ent_debug.returnPressed.connect(self.send_debug)
        btn_send = QPushButton("Send")
        btn_send.clicked.connect(self.send_debug)
        
        input_layout.addWidget(self.ent_debug)
        input_layout.addWidget(btn_send)
        
        layout.addWidget(self.txt_debug)
        layout.addLayout(input_layout)
        self.tabs.addTab(tab, "1: Debug")

    def setup_mode_2_linear(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        self.ent_linear_flow = QLineEdit()
        btn_start = QPushButton("Start")
        btn_start.clicked.connect(self.start_linear)
        
        layout.addRow("Flow (L/s):", self.ent_linear_flow)
        layout.addRow("", btn_start)
        self.tabs.addTab(tab, "2: Linear")

    def setup_mode_3_sinusoidal(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        self.ent_sin_amp = QLineEdit()
        self.ent_sin_freq = QLineEdit()
        btn_start = QPushButton("Start")
        btn_start.clicked.connect(self.start_sinusoidal)
        
        layout.addRow("Peak Flow (Amplitude):", self.ent_sin_amp)
        layout.addRow("Freq (Hz):", self.ent_sin_freq)
        layout.addRow("", btn_start)
        self.tabs.addTab(tab, "3: Sine")

    def setup_mode_4_calibration(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        self.ent_cal_start = QLineEdit()
        self.ent_cal_end = QLineEdit()
        self.ent_cal_steps = QLineEdit()
        btn_start = QPushButton("Start")
        btn_start.clicked.connect(self.start_calibration)
        
        layout.addRow("Start Flow:", self.ent_cal_start)
        layout.addRow("End Flow:", self.ent_cal_end)
        layout.addRow("Steps:", self.ent_cal_steps)
        layout.addRow("", btn_start)
        self.tabs.addTab(tab, "4: Calib.")

    def setup_mode_5_push(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        self.combo_push_dir = QComboBox()
        self.combo_push_dir.addItems(["Forward", "Backward"])
        
        self.ent_push_speed = QLineEdit()
        btn_start = QPushButton("Start")
        btn_start.clicked.connect(self.start_push)
        
        layout.addRow("Direction:", self.combo_push_dir)
        layout.addRow("Speed (Int):", self.ent_push_speed)
        layout.addRow("", btn_start)
        self.tabs.addTab(tab, "5: Push")

    def setup_mode_6_home(self):
        tab = QWidget()
        layout = QFormLayout(tab)
        
        self.combo_home_target = QComboBox()
        self.combo_home_target.addItems(["Start", "End"])
        
        btn_start = QPushButton("Start")
        btn_start.clicked.connect(self.start_home)
        
        layout.addRow("Home To:", self.combo_home_target)
        layout.addRow("", btn_start)
        self.tabs.addTab(tab, "6: Home")

    # ---------------------------------------------------------
    # BLE Async Operations (Using qasync)
    # ---------------------------------------------------------
    @asyncSlot()
    async def start_scan(self):
        self.lbl_status.setText("Status: Scanning...")
        self.lbl_status.setStyleSheet("color: orange; font-weight: bold;")
        self.btn_scan.setEnabled(False)
        self.combo_devices.clear()
        self.devices_dict.clear()

        try:
            devices = await BleakScanner.discover(timeout=5.0)
            auto_select_idx = -1
            
            for i, d in enumerate(devices):
                name = d.name or "Unknown"
                display_name = f"{name} - {d.address}"
                self.devices_dict[display_name] = d.address
                self.combo_devices.addItem(display_name)
                
                if name.startswith("Polmone") and auto_select_idx == -1:
                    auto_select_idx = i

            if auto_select_idx != -1:
                self.combo_devices.setCurrentIndex(auto_select_idx)
                
            self.lbl_status.setText("Status: Scan Complete")
            self.lbl_status.setStyleSheet("color: black; font-weight: bold;")
        except Exception as e:
            QMessageBox.critical(self, "Scan Error", str(e))
            self.lbl_status.setText("Status: Scan Failed")
        finally:
            self.btn_scan.setEnabled(True)

    @asyncSlot()
    async def connect_device(self):
        selection = self.combo_devices.currentText()
        if not selection: return
        address = self.devices_dict.get(selection)
        
        if address:
            self.lbl_status.setText("Status: Connecting...")
            self.lbl_status.setStyleSheet("color: orange; font-weight: bold;")
            self.btn_connect.setEnabled(False)
            
            try:
                self.client = BleakClient(address)
                await self.client.connect()
                await self.client.start_notify(UART_RX_CHAR_UUID, self._rx_handler)
                
                self.lbl_status.setText("Status: Connected")
                self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
                self.btn_disconnect.setEnabled(True)
            except Exception as e:
                self.lbl_status.setText("Status: Disconnected")
                self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
                self.btn_connect.setEnabled(True)
                QMessageBox.critical(self, "Connect Error", str(e))

    @asyncSlot()
    async def disconnect_device(self):
        self.btn_disconnect.setEnabled(False)
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        self.lbl_status.setText("Status: Disconnected")
        self.lbl_status.setStyleSheet("color: red; font-weight: bold;")
        self.btn_connect.setEnabled(True)
        self.stop_csv_logging()

    def send_cmd(self, text):
        if self.client and self.client.is_connected:
            asyncio.ensure_future(self.send_coro(text))

    async def send_coro(self, text):
        try:
            data = text.encode('utf-8')
            await self.client.write_gatt_char(UART_TX_CHAR_UUID, data)
        except Exception as e:
            QMessageBox.critical(self, "Send Error", str(e))

    def _rx_handler(self, sender, data):
        """Called by bleak when data arrives. We buffer and split it."""
        self.rx_buffer += data
        while b'\n' in self.rx_buffer:
            line, self.rx_buffer = self.rx_buffer.split(b'\n', 1)
            clean_line = line.replace(b'\r', b'').decode('utf-8', errors='ignore').strip()
            asyncio.get_event_loop().call_soon_threadsafe(self.process_rx_data, clean_line)

    # ---------------------------------------------------------
    # Data Processing & Plotting
    # ---------------------------------------------------------
    def process_rx_data(self, data_str):
        self.msg_counter += 1  # Increment the messages per second counter
        
        self.txt_debug.append(f"RX: {data_str}")

        if data_str.startswith("SNSR "):
            parts = data_str.split()
            try:
                # The raw incoming value is pressure
                pressure = float(parts[1])
                # Calculate Flow = Pressure * Resistance 
                flow = pressure * self.current_resistance 
                
                pos = float(parts[2])
                pwm = float(parts[3])
                time_ms = float(parts[4]) if len(parts) >= 5 else None

                if time_ms == -1.0:
                    self.is_calibrating = True
                    self.clear_plots()
                    self.start_csv_logging()
                elif time_ms == -2.0:
                    self.is_calibrating = False
                    self.stop_csv_logging()
                else:
                    if self.is_logging and time_ms is not None:
                        self.csv_writer.writerow([time_ms, flow, pos, pwm])
                    
                    # Process and plot the calculated flow
                    self.update_plots(flow, pos, pwm, time_ms)
            except (ValueError, IndexError):
                pass

    def update_plots(self, flow, pos, pwm, time_ms=None):
        # 1. Determine X-axis time value
        if self.is_calibrating and time_ms is not None:
            # During calibration, use the exact HM10 time (converted to seconds)
            t = time_ms / 1000.0
        else:
            # Normal modes: track local time
            t = time.time() - self.start_time

        # 2. Append new data
        self.t_data.append(t)
        self.flow_data.append(flow)
        self.pos_data.append(pos)
        self.pwm_data.append(pwm)

        # 3. If NOT calibrating, enforce the 10-second rolling window
        if not self.is_calibrating:
            cutoff_time = t - 10.0
            # Remove data older than 10 seconds
            while self.t_data and self.t_data[0] < cutoff_time:
                self.t_data.pop(0)
                self.flow_data.pop(0)
                self.pos_data.pop(0)
                self.pwm_data.pop(0)

        # 4. Update graph (if data exists)
        if self.t_data:
            self.line_flow.setData(self.t_data, self.flow_data)
            self.line_pos.setData(self.t_data, self.pos_data)
            self.line_pwm.setData(self.t_data, self.pwm_data)

    def clear_plots(self):
        self.t_data.clear()
        self.flow_data.clear()
        self.pos_data.clear()
        self.pwm_data.clear()
        
        self.line_flow.setData([], [])
        self.line_pos.setData([], [])
        self.line_pwm.setData([], [])

    # ---------------------------------------------------------
    # Message Rate Updating
    # ---------------------------------------------------------
    def update_mps(self):
        """Called every second by the QTimer to update the UI and reset the counter."""
        self.lbl_mps.setText(f"{self.msg_counter} msg/s")
        self.msg_counter = 0

    # ---------------------------------------------------------
    # CSV Handling
    # ---------------------------------------------------------
    def start_csv_logging(self):
        if self.is_logging: return
        filename = f"calibration_{int(time.time())}.csv"
        self.csv_file = open(filename, mode='w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(["Time(ms)", "Flow(L/s)", "Position(ticks)", "PWM(%)"])
        self.is_logging = True
        self.lbl_status.setText(f"Status: Logging to {filename}...")
        self.lbl_status.setStyleSheet("color: blue; font-weight: bold;")

    def stop_csv_logging(self):
        if not self.is_logging: return
        self.is_logging = False
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
        self.lbl_status.setText("Status: Connected (Logging stopped)")
        self.lbl_status.setStyleSheet("color: green; font-weight: bold;")

    # ---------------------------------------------------------
    # System Overrides for Clean State Transitions
    # ---------------------------------------------------------
    def _cancel_calibration_state(self):
        """Called when a user manually triggers another mode during a calibration"""
        if self.is_calibrating:
            self.is_calibrating = False
            self.stop_csv_logging()

    # ---------------------------------------------------------
    # UI Command Methods
    # ---------------------------------------------------------
    def send_resistance(self):
        res_str = self.ent_resistance.text()
        try:
            self.current_resistance = float(res_str)
            self.send_cmd(f"R: {self.current_resistance}\n")
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Resistance must be a valid number.")

    def send_stop(self):
        self._cancel_calibration_state()
        self.send_cmd("STOP\n")

    def send_self_test(self):
        self._cancel_calibration_state()
        self.send_cmd("Mode 127\n")

    def send_debug(self):
        self._cancel_calibration_state()
        text = self.ent_debug.text()
        if text:
            self.send_cmd(text + "\n")
            self.ent_debug.clear()

    def start_linear(self):
        self._cancel_calibration_state()
        flow = self.ent_linear_flow.text()
        if flow: self.send_cmd(f"Mode 0 {flow}\n")

    def start_sinusoidal(self):
        self._cancel_calibration_state()
        amp = self.ent_sin_amp.text()
        freq = self.ent_sin_freq.text()
        if amp and freq: self.send_cmd(f"Mode 1 {amp} {freq}\n")

    def start_calibration(self):
        self._cancel_calibration_state()
        start_flow = self.ent_cal_start.text()
        end_flow = self.ent_cal_end.text()
        steps = self.ent_cal_steps.text()
        if start_flow and end_flow and steps:
            self.send_cmd(f"Mode 2 {start_flow} {end_flow} {steps}\n")

    def start_push(self):
        self._cancel_calibration_state()
        speed_str = self.ent_push_speed.text()
        if not speed_str: return
        
        direction_text = self.combo_push_dir.currentText()
        direction_val = 1 if direction_text == "Forward" else 0
        
        try:
            speed = int(speed_str)
            self.send_cmd(f"Mode 3 {speed} {direction_val}\n")
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Speed must be an integer.")

    def start_home(self):
        self._cancel_calibration_state()
        target_text = self.combo_home_target.currentText()
        target_val = 0 if target_text == "Start" else 1
        self.send_cmd(f"Mode 4 {target_val}\n")

    async def closeEvent(self, event):
        """Handle window close event properly."""
        if self.client and self.client.is_connected:
            await self.client.disconnect()
        if self.is_logging:
            self.stop_csv_logging()
        event.accept()

# ---------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    main_window = HM10App()
    main_window.show()
    QTimer.singleShot(0, main_window.btn_scan.click)

    with loop:
        loop.run_forever()