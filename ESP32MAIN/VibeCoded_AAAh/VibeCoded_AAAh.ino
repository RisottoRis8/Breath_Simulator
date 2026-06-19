#include <Wire.h>
#include <SPI.h>
#include <ESP32Encoder.h>
#include <NimBLEDevice.h>

// ── CONFIGURAZIONE PINOUT ────────────────────────────────────────
#define UART_TX     17
#define UART_RX     16
#define ENC_A       34
#define ENC_B       35
#define ENC_Z        4       // Dichiarato ma non utilizzato
#define PWM_OUT     15
#define GPIO_OUT_1  26       // EN (Driver Motore)
#define GPIO_OUT_2  25       // DIR (Driver Motore)
#define GPIO_IRQ_1  32       // Limit Switch 1 (Home)
#define GPIO_IRQ_2  33       // Limit Switch 2 (End)
#define GPIO_OUT_3  27       // Ausiliario
#define GPIO_OUT_4  14       // Ausiliario
#define GPIO_IN_1   39       // Ausiliario
#define GPIO_IN_2   13       // Ausiliario
#define I2C_SDA     21
#define I2C_SCL     22
#define PIN_CS      5        // SPI CS per EEPROM

// ── COSTANTI EEPROM & SENSORI ────────────────────────────────────
#define EEPROM_WREN   0x06
#define EEPROM_WRITE  0x02
#define EEPROM_READ   0x03
#define SDP_ADDR      0x25
#define SFM_ADDR      0x40

const float SDP_SCALE_FACTOR = 60.0;
const float SFM_SCALE_FACTOR = 120.0;
const uint16_t SFM_OFFSET = 32768;

// ── UUID BLUETOOTH (UART Custom) ─────────────────────────────────
#define SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_RX "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_TX "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

// ── STRUTTURA DATI MEMORIA (EEPROM) ──────────────────────────────
struct Config {
    float Kp[3]; // 0: SDP, 1: SFM, 2: ENC
    float Ki[3];
    float Kd[3];
    uint8_t active_sensor;
    float firmware_version;
    float syringe_area;
    float syringe_length;
    float fluid_resistance;
} sys_config;

// ── VARIABILI DI STATO GLOBALI ───────────────────────────────────
ESP32Encoder encoder;
hw_timer_t *timer = NULL;
NimBLECharacteristic* pTxCharacteristic;

volatile bool tick_200hz = false;
volatile bool emergency_stop = false;
long max_ticks = 10000;

enum OpMode { MODE_IDLE, MODE_CONST, MODE_SINE, MODE_CALIB, MODE_DEBUG };
OpMode current_mode = MODE_IDLE;

float current_flow = 0.0;
float current_pressure = 0.0;
float target_flow_setpoint = 0.0;
int manual_pwm_input = 0;

// Variabili PID & Calibrazione
float integral_err = 0.0, prev_err = 0.0;
uint32_t telemetry_timer = 0;
float cal_sum_pressure = 0.0;
float cal_sum_flow = 0.0;
uint32_t cal_samples = 0;

// ── INTERRUPT ────────────────────────────────────────────────────
void IRAM_ATTR onTimer() {
    tick_200hz = true;
}

void IRAM_ATTR limitSwitchISR() {
    emergency_stop = true;
    ledcWrite(PWM_OUT, 0);   // Modificato per Core 3.x
    digitalWrite(GPIO_OUT_1, LOW); // Disabilita driver H-Bridge
}

// ── DRIVER SPI EEPROM (25AA256) ──────────────────────────────────
void eeprom_write_enable() {
    digitalWrite(PIN_CS, LOW);
    SPI.transfer(EEPROM_WREN);
    digitalWrite(PIN_CS, HIGH);
}

void saveConfigToEEPROM() {
    eeprom_write_enable();
    delay(5);
    digitalWrite(PIN_CS, LOW);
    SPI.transfer(EEPROM_WRITE);
    SPI.transfer(0x00); 
    SPI.transfer(0x00); 
    
    uint8_t* ptr = (uint8_t*)&sys_config;
    for (size_t i = 0; i < sizeof(Config); i++) {
        SPI.transfer(ptr[i]);
    }
    digitalWrite(PIN_CS, HIGH);
    delay(10);
}

void loadConfigFromEEPROM() {
    digitalWrite(PIN_CS, LOW);
    SPI.transfer(EEPROM_READ);
    SPI.transfer(0x00);
    SPI.transfer(0x00);
    
    uint8_t* ptr = (uint8_t*)&sys_config;
    for (size_t i = 0; i < sizeof(Config); i++) {
        ptr[i] = SPI.transfer(0x00);
    }
    digitalWrite(PIN_CS, HIGH);
    
    if (isnan(sys_config.firmware_version) || sys_config.firmware_version <= 0) {
        sys_config.firmware_version = 1.0;
        sys_config.active_sensor = 2; // Default Encoder
        sys_config.syringe_area = 5.0;
        sys_config.syringe_length = 0.1;
        sys_config.fluid_resistance = 1.0;
        for(int i=0; i<3; i++) { sys_config.Kp[i]=1.0; sys_config.Ki[i]=0.1; sys_config.Kd[i]=0.01; }
        saveConfigToEEPROM();
    }
}

// ── DRIVER I2C SENSIRION (BARE-METAL) ────────────────────────────
void initSensorsRaw() {
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000); 

    // Start SDP810
    Wire.beginTransmission(SDP_ADDR);
    Wire.write(0x36); Wire.write(0x15);
    Wire.endTransmission();

    // Start SFM3300
    Wire.beginTransmission(SFM_ADDR);
    Wire.write(0x10); Wire.write(0x00);
    Wire.endTransmission();
    delay(100);
}

void readSDP_Raw() {
    Wire.requestFrom((uint16_t)SDP_ADDR, (uint8_t)3, (uint8_t)true);
    if (Wire.available() >= 2) {
        int16_t raw_pres = (Wire.read() << 8) | Wire.read();
        Wire.read();
        current_pressure = (float)raw_pres / SDP_SCALE_FACTOR;
    }
}

void readSFM_Raw() {
    Wire.requestFrom((uint16_t)SFM_ADDR, (uint8_t)3, (uint8_t)true);
    if (Wire.available() >= 2) {
        uint16_t raw_flow = (Wire.read() << 8) | Wire.read();
        Wire.read();
        current_flow = ((float)raw_flow - SFM_OFFSET) / SFM_SCALE_FACTOR;
    }
}

// ── PARSER UNIFICATO (BLE, USB, UART) ────────────────────────────
void processCommand(String cmd) {
    cmd.trim();
    if (cmd.length() == 0) return;
    
    Serial.println("[CMD RX] " + cmd);
    Serial2.println("[CMD RX] " + cmd);

    if (cmd.startsWith("SET_MODE:")) {
        current_mode = (OpMode)cmd.substring(9).toInt();
        integral_err = 0; prev_err = 0;
        cal_sum_pressure = 0; cal_sum_flow = 0; cal_samples = 0;
    } 
    else if (cmd.startsWith("SET_FLOW:")) {
        target_flow_setpoint = cmd.substring(9).toFloat();
    } 
    else if (cmd.startsWith("SET_PWM:")) {
        manual_pwm_input = cmd.substring(8).toInt();
    }
    else if (cmd.startsWith("SET_SENS:")) {
        sys_config.active_sensor = cmd.substring(9).toInt();
    }
    else if (cmd.startsWith("CONFIG:")) {
        int idx = cmd.indexOf(':') + 1;
        int comma1 = cmd.indexOf(',', idx);
        int comma2 = cmd.indexOf(',', comma1 + 1);
        int comma3 = cmd.indexOf(',', comma2 + 1);
        int comma4 = cmd.indexOf(',', comma3 + 1);
        int comma5 = cmd.indexOf(',', comma4 + 1);
        int comma6 = cmd.indexOf(',', comma5 + 1);
        
        int s_idx = cmd.substring(idx, comma1).toInt();
        sys_config.Kp[s_idx] = cmd.substring(comma1+1, comma2).toFloat();
        sys_config.Ki[s_idx] = cmd.substring(comma2+1, comma3).toFloat();
        sys_config.Kd[s_idx] = cmd.substring(comma3+1, comma4).toFloat();
        sys_config.syringe_area = cmd.substring(comma4+1, comma5).toFloat();
        sys_config.syringe_length = cmd.substring(comma5+1, comma6).toFloat();
        sys_config.fluid_resistance = cmd.substring(comma6+1).toFloat();
        saveConfigToEEPROM();
        
        Serial.println("[CONFIG] EEPROM Aggiornata");
        Serial2.println("[CONFIG] EEPROM Aggiornata");
    }
    else if (cmd == "RESET_ERR") {
        emergency_stop = false;
        digitalWrite(GPIO_OUT_1, HIGH);
    }
}

class MyCallbacks: public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* pCharacteristic) {
        std::string value = pCharacteristic->getValue();
        if (value.length() > 0) {
            processCommand(String(value.c_str()));
        }
    }
};

void checkSerialInput() {
    if (Serial.available()) {
        processCommand(Serial.readStringUntil('\n'));
    }
    if (Serial2.available()) {
        processCommand(Serial2.readStringUntil('\n'));
    }
}

void initBLE() {
    NimBLEDevice::init("SyringePump_BLE");
    NimBLEServer *pServer = NimBLEDevice::createServer();
    NimBLEService *pService = pServer->createService(SERVICE_UUID);
    pTxCharacteristic = pService->createCharacteristic(CHARACTERISTIC_UUID_TX, NIMBLE_PROPERTY::NOTIFY);
    NimBLECharacteristic *pRxCharacteristic = pService->createCharacteristic(CHARACTERISTIC_UUID_RX, NIMBLE_PROPERTY::WRITE);
    
    pRxCharacteristic->setCallbacks(new MyCallbacks());
    pService->start();
    pServer->getAdvertising()->start();
}

// ── HOMING E SELF-TEST ───────────────────────────────────────────
void performSelfTest() {
    digitalWrite(GPIO_OUT_1, HIGH);
    
    digitalWrite(GPIO_OUT_2, LOW);
    ledcWrite(PWM_OUT, 38);  // Modificato per Core 3.x
    
    uint32_t timeout = millis();
    while(digitalRead(GPIO_IRQ_1) == HIGH) {
        if(millis() - timeout > 10000) break;
        delay(5);
    }
    ledcWrite(PWM_OUT, 0);
    delay(300);
    encoder.clearCount();
    
    digitalWrite(GPIO_OUT_2, HIGH);
    ledcWrite(PWM_OUT, 38);
    
    timeout = millis();
    while(digitalRead(GPIO_IRQ_2) == HIGH) {
        if(millis() - timeout > 10000) break;
        delay(5);
    }
    ledcWrite(PWM_OUT, 0);
    
    max_ticks = encoder.getCount();
    delay(300);
    
    digitalWrite(GPIO_OUT_2, LOW);
    ledcWrite(PWM_OUT, 40);
    delay(500);
    ledcWrite(PWM_OUT, 0);
    
    emergency_stop = false;
}

// ── SETUP ────────────────────────────────────────────────────────
void setup() {
    Serial.begin(230400);
    Serial2.begin(230400, SERIAL_8N1, UART_RX, UART_TX);
    
    pinMode(GPIO_OUT_1, OUTPUT);
    pinMode(GPIO_OUT_2, OUTPUT);
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    
    pinMode(GPIO_IRQ_1, INPUT_PULLUP);
    pinMode(GPIO_IRQ_2, INPUT_PULLUP);
    
    SPI.begin();
    loadConfigFromEEPROM();
    initSensorsRaw();
    
    // Aggiornato per rimuovere il macro UP deprecato
    pinMode(ENC_A, INPUT_PULLUP);
    pinMode(ENC_B, INPUT_PULLUP);
    encoder.attachHalfQuad(ENC_A, ENC_B); 

    // Aggiornato PWM per Core 3.x: unificato ledcAttach
    ledcAttach(PWM_OUT, 5000, 8);

    initBLE();
    performSelfTest();

    attachInterrupt(GPIO_IRQ_1, limitSwitchISR, FALLING);
    attachInterrupt(GPIO_IRQ_2, limitSwitchISR, FALLING);

    // Aggiornato Timer per Core 3.x
    timer = timerBegin(1000000); // 1 MHz di frequenza nativa
    timerAttachInterrupt(timer, &onTimer); // Rimosso l'argomento 'edge'
    timerAlarm(timer, 5000, true, 0); // 5000 µs, autoreload=true, repeat count=0 (infinito)
}

// ── LOOP PRINCIPALE ──────────────────────────────────────────────
void loop() {
    checkSerialInput();

    if (tick_200hz) {
        tick_200hz = false;

        readSDP_Raw();
        readSFM_Raw();
        long encoder_pos = encoder.getCount();

        if (sys_config.active_sensor == 0) {
            current_flow = current_pressure / sys_config.fluid_resistance;
        } 
        else if (sys_config.active_sensor == 1) {
            // current_flow già aggiornato
        } 
        else {
            static long last_pos = 0;
            float velocity_ticks_sec = (encoder_pos - last_pos) * 200.0;
            float velocity_m_s = velocity_ticks_sec * (sys_config.syringe_length / max_ticks);
            current_flow = sys_config.syringe_area * velocity_m_s;
            last_pos = encoder_pos;
        }

        if (emergency_stop) {
            ledcWrite(PWM_OUT, 0); // Modificato per Core 3.x
            return;
        }

        float setpoint = 0.0;
        static bool direction_toggle = true;
        long soft_margin = max_ticks * 0.08;

        if (current_mode == MODE_CONST || current_mode == MODE_SINE) {
            if (direction_toggle && (encoder_pos >= (max_ticks - soft_margin))) {
                direction_toggle = false; integral_err = 0;
            } else if (!direction_toggle && (encoder_pos <= soft_margin)) {
                direction_toggle = true; integral_err = 0;
            }
        }

        if (current_mode == MODE_CONST) {
            setpoint = direction_toggle ? target_flow_setpoint : -target_flow_setpoint;
        } 
        else if (current_mode == MODE_SINE) {
            float phase = map(encoder_pos, 0, max_ticks, 0, 180) * (PI / 180.0);
            setpoint = direction_toggle ? (target_flow_setpoint * sin(phase)) : (-target_flow_setpoint * sin(phase));
        }
        else if (current_mode == MODE_CALIB) {
            if (encoder_pos < (max_ticks - soft_margin)) {
                digitalWrite(GPIO_OUT_2, HIGH);
                ledcWrite(PWM_OUT, manual_pwm_input);
                cal_sum_pressure += current_pressure;
                cal_sum_flow += current_flow;
                cal_samples++;
            } else {
                ledcWrite(PWM_OUT, 0);
                if (cal_samples > 0 && (cal_sum_flow / cal_samples) > 0.01) {
                    sys_config.fluid_resistance = (cal_sum_pressure / cal_samples) / (cal_sum_flow / cal_samples);
                    saveConfigToEEPROM();
                }
                current_mode = MODE_IDLE;
            }
            return;
        }
        else if (current_mode == MODE_DEBUG) {
            digitalWrite(GPIO_OUT_2, manual_pwm_input >= 0 ? HIGH : LOW);
            int raw_pwm = map(abs(manual_pwm_input), 0, 100, 25, 230);
            ledcWrite(PWM_OUT, constrain(raw_pwm, 0, 230));
            return;
        }
        else {
            ledcWrite(PWM_OUT, 0);
            return;
        }

        uint8_t active_s = sys_config.active_sensor;
        float error = setpoint - current_flow;
        integral_err += error * 0.005;
        integral_err = constrain(integral_err, -50.0, 50.0);
        float derivative_err = (error - prev_err) / 0.005;
        prev_err = error;

        float pid_output = (sys_config.Kp[active_s] * error) + 
                           (sys_config.Ki[active_s] * integral_err) + 
                           (sys_config.Kd[active_s] * derivative_err);

        float soft_scaling = 1.0;
        if (encoder_pos < soft_margin) soft_scaling = (float)encoder_pos / soft_margin;
        else if ((max_ticks - encoder_pos) < soft_margin) soft_scaling = (float)(max_ticks - encoder_pos) / soft_margin;
        soft_scaling = constrain(soft_scaling, 0.1, 1.0);
        pid_output *= soft_scaling;

        digitalWrite(GPIO_OUT_2, pid_output >= 0 ? HIGH : LOW);
        int final_pwm = map(abs((int)pid_output), 0, 100, 25, 230);
        ledcWrite(PWM_OUT, constrain(final_pwm, 25, 230));
    }

    if (millis() - telemetry_timer > 100) {
        telemetry_timer = millis();
        String telemetry_pack = String(current_flow, 3) + "," + 
                                String(current_pressure, 3) + "," + 
                                String(encoder.getCount()) + "," + 
                                String((int)current_mode) + "," +
                                String(sys_config.fluid_resistance, 3) + "," +
                                String(emergency_stop ? 1 : 0);
                                
        Serial.println(telemetry_pack);
        Serial2.println(telemetry_pack);
        
        // Rimosso getSubscribedCount() in favore del semplice notify()
        pTxCharacteristic->setValue(telemetry_pack.c_str());
        pTxCharacteristic->notify();
    }
}