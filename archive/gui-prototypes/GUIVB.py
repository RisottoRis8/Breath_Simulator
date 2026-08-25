import sys
import asyncio
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QLineEdit, QGroupBox, QGridLayout, QStatusBar)
from PyQt6.QtCore import Qt
from qasync import QEventLoop
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
CHARACTERISTIC_UUID_RX = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
CHARACTERISTIC_UUID_TX = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

class SyringePumpApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Syringe Pump Control System - Medical Engineering")
        self.resize(750, 550)
        self.client = None
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()

        # ── PANNELLO SINISTRO: TELEMETRIA ────────────────────────────────
        left_panel = QVBoxLayout()
        
        telemetry_group = QGroupBox("Telemetria Real-Time")
        tele_layout = QGridLayout()
        
        self.lbl_flow = QLabel("0.000 slm")
        self.lbl_flow.setStyleSheet("font-size: 24px; font-weight: bold; color: #007ACC;")
        self.lbl_press = QLabel("0.000 Pa")
        self.lbl_press.setStyleSheet("font-size: 24px; font-weight: bold; color: #D62728;")
        self.lbl_pos = QLabel("0 ticks")
        self.lbl_pos.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.lbl_mode = QLabel("IDLE")
        self.lbl_mode.setStyleSheet("font-size: 16px; font-weight: bold; color: #2CA02C;")
        self.lbl_res = QLabel("1.000 R")
        
        tele_layout.addWidget(QLabel("Flusso Attuale:"), 0, 0)
        tele_layout.addWidget(self.lbl_flow, 0, 1)
        tele_layout.addWidget(QLabel("Pressione Differenziale:"), 1, 0)
        tele_layout.addWidget(self.lbl_press, 1, 1)
        tele_layout.addWidget(QLabel("Posizione Meccanica (Encoder):"), 2, 0)
        tele_layout.addWidget(self.lbl_pos, 2, 1)
        tele_layout.addWidget(QLabel("Stato Ciclo/Modo uC:"), 3, 0)
        tele_layout.addWidget(self.lbl_mode, 3, 1)
        tele_layout.addWidget(QLabel("Resistenza Fluidica Stimata:"), 4, 0)
        tele_layout.addWidget(self.lbl_res, 4, 1)
        
        telemetry_group.setLayout(tele_layout)
        left_panel.addWidget(telemetry_group)

        # Connessione BLE
        self.btn_connect = QPushButton("Connetti via Bluetooth")
        self.btn_connect.clicked.connect(self.trigger_connect)
        left_panel.addWidget(self.btn_connect)
        
        self.btn_reset_err = QPushButton("Sblocca Arresto Emergenza")
        self.btn_reset_err.setStyleSheet("background-color: #FFA500; color: black; font-weight: bold;")
        self.btn_reset_err.clicked.connect(lambda: self.send_raw_cmd("RESET_ERR"))
        left_panel.addWidget(self.btn_reset_err)

        # ── PANNELLO DESTRO: CONTROLLI E PARAMETRI ───────────────────────
        right_panel = QVBoxLayout()

        # Selezione Modalità Operativa
        mode_group = QGroupBox("Comandi di Controllo Profili")
        mode_layout = QVBoxLayout()
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["IDLE / ARRESTO", "Flusso Costante (PID)", "Flusso Sinusoidale (PID)", "Calibrazione Automatica", "Manuale / Debug"])
        self.combo_mode.currentIndexChanged.connect(self.change_mode)
        mode_layout.addWidget(QLabel("Seleziona Profilo Sperimentale:"))
        mode_layout.addWidget(self.combo_mode)

        # Setpoint dinamici
        self.txt_setpoint = QLineEdit("50.0")
        mode_layout.addWidget(QLabel("Target Flusso Setpoint (slm):"))
        mode_layout.addWidget(self.txt_setpoint)
        
        self.txt_manual_pwm = QLineEdit("30")
        mode_layout.addWidget(QLabel("Valore PWM Diretto / Calibrazione (0-100%):"))
        mode_layout.addWidget(self.txt_manual_pwm)
        
        btn_apply_setpoint = QPushButton("Invia Parametri Operativi")
        btn_apply_setpoint.clicked.connect(self.apply_operation_params)
        mode_layout.addWidget(btn_apply_setpoint)
        
        mode_group.setLayout(mode_layout)
        right_panel.addWidget(mode_group)

        # Parametri di calibrazione e PID (EEPROM)
        config_group = QGroupBox("Configurazione Parametri Regolazione (EEPROM)")
        config_layout = QGridLayout()
        
        self.combo_sensor_select = QComboBox()
        self.combo_sensor_select.addItems(["SDP810 (Pressione)", "SFM3300 (Flusso Diretto)", "Encoder Hardware"])
        self.combo_sensor_select.currentIndexChanged.connect(self.update_active_sensor_uc)
        
        self.txt_kp = QLineEdit("1.5")
        self.txt_ki = QLineEdit("0.2")
        self.txt_kd = QLineEdit("0.05")
        self.txt_area = QLineEdit("12.56")
        self.txt_length = QLineEdit("0.15")
        self.txt_res_init = QLineEdit("1.2")
        
        config_layout.addWidget(QLabel("Anello di Chiusura su:"), 0, 0, 1, 2)
        config_layout.addWidget(self.combo_sensor_select, 1, 0, 1, 2)
        config_layout.addWidget(QLabel("Proporzionale (Kp):"), 2, 0)
        config_layout.addWidget(self.txt_kp, 2, 1)
        config_layout.addWidget(QLabel("Integrale (Ki):"), 3, 0)
        config_layout.addWidget(self.txt_ki, 3, 1)
        config_layout.addWidget(QLabel("Derivativo (Kd):"), 4, 0)
        config_layout.addWidget(self.txt_kd, 4, 1)
        config_layout.addWidget(QLabel("Area Siringa (cm²):"), 5, 0)
        config_layout.addWidget(self.txt_area, 5, 1)
        config_layout.addWidget(QLabel("Corsa Utile (m):"), 6, 0)
        config_layout.addWidget(self.txt_length, 6, 1)
        config_layout.addWidget(QLabel("Resistenza Base:"), 7, 0)
        config_layout.addWidget(self.txt_res_init, 7, 1)
        
        btn_save_config = QPushButton("Flash Configurazione su ESP32")
        btn_save_config.setStyleSheet("background-color: #4CAF50; color: white;")
        btn_save_config.clicked.connect(self.flash_eeprom_config)
        config_layout.addWidget(btn_save_config, 8, 0, 1, 2)

        config_group.setLayout(config_layout)
        right_panel.addWidget(config_group)

        main_layout.addLayout(left_panel, 40)
        main_layout.addLayout(right_panel, 60)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Stato: Disconnesso")

    # ── LOGICA ASINCRONA DI RETE BLE ──────────────────────────────────
    def trigger_connect(self):
        asyncio.ensure_future(self.connect_ble_device())

    async def connect_ble_device(self):
        self.status_bar.showMessage("Stato: Scansione periferiche in corso...")
        devices = await BleakScanner.discover()
        target = next((d for d in devices if d.name == "SyringePump_BLE"), None)
        
        if target:
            self.status_bar.showMessage(f"Stato: Accoppiamento con {target.address}...")
            self.client = BleakClient(target.address)
            try:
                await self.client.connect()
                self.status_bar.showMessage("Stato: Sistema Online (Connesso via BLE)")
                self.btn_connect.setText("Disconnetti")
                await self.client.start_notify(CHARACTERISTIC_UUID_TX, self.handle_incoming_telemetry)
            except Exception as e:
                self.status_bar.showMessage(f"Errore critico di connessione: {e}")
        else:
            self.status_bar.showMessage("Stato: Errore. uC non rilevato. Verifica alimentazione.")

    def handle_incoming_telemetry(self, sender, data):
        try:
            payload = data.decode('utf-8').split(',')
            if len(payload) >= 6:
                flow, pressure, ticks, mode, resistance, emergency = payload
                
                self.lbl_flow.setText(f"{flow} slm")
                self.lbl_press.setText(f"{pressure} Pa")
                self.lbl_pos.setText(f"{ticks} ticks")
                self.lbl_res.setText(f"{resistance} R")
                
                mode_mapping = ["IDLE", "FLUSSO COSTANTE", "SENOIDALE", "CALIBRAZIONE AUTOMATICA", "DEBUG MANUALE"]
                m_idx = int(mode)
                if m_idx < len(mode_mapping):
                    self.lbl_mode.setText(mode_mapping[m_idx])
                
                if int(emergency) == 1:
                    self.status_bar.showMessage("ALLARME CRITICO: ARRESTO DA MICROSWITCH!")
                    self.status_bar.setStyleSheet("background-color: #FFD2D2; color: red;")
                else:
                    self.status_bar.setStyleSheet("")
        except Exception as e:
            print(f"Errore parsing telemetria: {e}")

    def send_raw_cmd(self, command_str):
        if self.client and self.client.is_connected:
            asyncio.ensure_future(self.client.write_gatt_char(CHARACTERISTIC_UUID_RX, command_str.encode('utf-8')))

    def change_mode(self, idx):
        self.send_raw_cmd(f"SET_MODE:{idx}")

    def apply_operation_params(self):
        flow = self.txt_setpoint.text()
        pwm = self.txt_manual_pwm.text()
        self.send_raw_cmd(f"SET_FLOW:{flow}")
        self.send_raw_cmd(f"SET_PWM:{pwm}")

    def update_active_sensor_uc(self, idx):
        self.send_raw_cmd(f"SET_SENS:{idx}")

    def flash_eeprom_config(self):
        sens_idx = self.combo_sensor_select.currentIndex()
        kp = self.txt_kp.text()
        ki = self.txt_ki.text()
        kd = self.txt_kd.text()
        area = self.txt_area.text()
        length = self.txt_length.text()
        res = self.txt_res_init.text()
        
        # Genera pacchetto serializzato
        cmd = f"CONFIG:{sens_idx},{kp},{ki},{kd},{area},{length},{res}"
        self.send_raw_cmd(cmd)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    gui = SyringePumpApp()
    gui.show()
    
    with loop:
        loop.run_forever()