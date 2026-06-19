#include <Wire.h>
#include <SPI.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <math.h>

// ── UART ─────────────────────────────────────────────────────────
#define UART_TX     17
#define UART_RX     16

// ── ENCODER ──────────────────────────────────────────────────────
#define ENC_A       34
#define ENC_B       35
#define ENC_Z        4

// ── PWM + 2 GPIO OUT ─────────────────────────────────────────────
#define PWM_OUT     15
#define GPIO_OUT_1  25       // EN
#define GPIO_OUT_2  26       // DIR

// ── 2 GPIO IN con INTERRUPT ──────────────────────────────────────
#define GPIO_IRQ_1  32
#define GPIO_IRQ_2  33

// ── 2 GPIO OUT aggiuntivi ────────────────────────────────────────
#define GPIO_OUT_3  27
#define GPIO_OUT_4  14

// ── 2 GPIO IN aggiuntivi ─────────────────────────────────────────
#define GPIO_IN_1   39
#define GPIO_IN_2   13

// ── I2C ──────────────────────────────────────────────────────────
#define SDP_ADDR    0x25
#define SFM_ADDR    0x40
#define I2C_SDA     21
#define I2C_SCL     22

// ── SPI / EEPROM ─────────────────────────────────────────────────
#define PIN_CS      5
#define EEPROM_WREN   0x06
#define EEPROM_RDSR   0x05
#define EEPROM_WRITE  0x02
#define EEPROM_READ   0x03
#define EEPROM_PAGE_SIZE   64
#define EEPROM_TOTAL_SIZE  32768

SPIClass vspi(VSPI);
SPISettings eepromSettings(1000000, MSBFIRST, SPI_MODE0);

static inline void CS_Low()  { digitalWrite(PIN_CS, LOW);  }
static inline void CS_High() { digitalWrite(PIN_CS, HIGH); }

// ── Costanti di conversione ───────────────────────────────────────
const float SDP_SCALE_FACTOR = 60.0f;
const float SFM_SCALE_FACTOR = 120.0f;
const int16_t SFM_OFFSET     = 32768;

// ── Tipo di sensore ───────────────────────────────────────────────
enum TipoSensore { NESSUNO, SDP810, SFM3300 };
TipoSensore sensoreAttivo = NESSUNO;

// ── Stati del Sistema ─────────────────────────────────────────────
enum Modalita {
    MODE_DEBUG = 1000,
    MODE_LINEAR = 0,
    MODE_SINUSOIDAL = 1,
    MODE_CALIBRATION = 2,
    MODE_PUSH = 3,
    MODE_HOME = 4,
    MODE_IDLE = 5
};
volatile Modalita stato = MODE_IDLE; // Stato iniziale di sicurezza

// ── Variabili PID e Target ────────────────────────────────────────
float Kp = 1.0f;
float Ki = 0.1f;
float Kd = 0.05f;

float integral = 0.0f;
float prev_error = 0.0f;
unsigned long prev_time_pid = 0;

float target_flow = 0.0f;     // Per Mode 0 (L/s)
float sine_amplitude = 0.0f;  // Per Mode 1 (L/s)
float sine_frequency = 0.0f;  // Per Mode 1 (Hz)
unsigned long start_time_mode1 = 0;
int divisore;
int pwmValue;
    float current_flow = 0.0f;

// ── BLE HM10 Config ───────────────────────────────────────────────
#define HM10_SERVICE_UUID      "0000FFE0-0000-1000-8000-00805F9B34FB"
#define HM10_UART_CHAR_UUID    "0000FFE1-0000-1000-8000-00805F9B34FB"

BLEServer *pServer = NULL;
BLECharacteristic * pTxCharacteristic = NULL;
bool deviceConnected = false;
String msg_BLE = ""; // Buffer per i messaggi BLE in arrivo

// ── Variabili "dummy" per il parser ───────────────────────────────
int parametri_int[5] = {0};
float parametri_float[5] = {0.0};
char msg[128] = "";
bool read_SDP810 = false;
void SFM3300_Start() {} 
void SFM3300_Stop() {}  
void I2C_Scan() {}      
float resistenza = 1.0f; // Inizializzata qui, NON dentro il loop!

// ── Timer hardware 200 Hz ─────────────────────────────────────────
hw_timer_t* timer200Hz = nullptr;
volatile bool campiona  = false;

// ── Timer stampa EEPROM ───────────────────────────────────────────
unsigned long ultimo_tempo_stampa_ms = 0;
const unsigned long INTERVALLO_STAMPA_MS = 1000;
String stringaRicevuta = "";

// ── VARIABILI ENCODER ─────────────────────────────────────────────
volatile long encoder_pos = 0; // Posizione attuale dell'encoder

// ── Dichiarazioni ─────────────────────────────────────────────────
TipoSensore rilevaSensore();
float leggi_SDP810();
float leggi_SFM3300();
void EEPROM_SPI_Init();
void write_EEPROM(const char* str);
char* read_EEPROM();
static void EEPROM_WaitReady();
static void EEPROM_WriteEnable();
void parser();
void setMotor(float speed, bool dir, bool enable);
void send_BLE(const String& messaggio);

/* ══════════════════════════════════════════════════════════════
 * ISR (Interrupt Service Routines)
 * ══════════════════════════════════════════════════════════════ */
void IRAM_ATTR onTimer200Hz() {
    campiona = true;
}

// ISR per lo stop immediato di emergenza dai pin di ingresso hardware
void IRAM_ATTR onEmergencyStop() {
    stato = MODE_IDLE;
    digitalWrite(GPIO_OUT_1, LOW); // Disabilita motore
    analogWrite(PWM_OUT, 0);       // Spegne il segnale PWM
}

// ISR per leggere l'encoder in quadratura
void IRAM_ATTR onEncoderISR() {
    // Tabella di lookup per decodificare la quadratura in modo ultra-veloce
    static int8_t lookup_table[] = {0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0};
    static uint8_t enc_val = 0;
    
    enc_val = enc_val << 2;
    enc_val = enc_val | ((digitalRead(ENC_A) << 1) | digitalRead(ENC_B));
    
    encoder_pos += lookup_table[enc_val & 0b1111];
}

/* ══════════════════════════════════════════════════════════════
 * BLE CALLBACKS
 * ══════════════════════════════════════════════════════════════ */
class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
    };
    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      pServer->startAdvertising(); // Riavvia l'advertising per nuove connessioni
    }
};

class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      String rxValue = pCharacteristic->getValue(); 
      
      if (rxValue.length() > 0) {
        Serial.print(rxValue); 
        
        for (int i = 0; i < rxValue.length(); i++) {
          char c = rxValue[i];
          if (c == '\n' || c == '\r') {
            if (msg_BLE.length() > 0) {
              parser();
              msg_BLE = ""; 
            }
          } else {
            msg_BLE += c;
          }
        }
      }
    }
};

/* ══════════════════════════════════════════════════════════════
 * SETUP
 * ══════════════════════════════════════════════════════════════ */
void setup()
{
    Serial.begin(115200);
    while (!Serial) { delay(10); }
    delay(2000);
    divisore = 0;
    pwmValue = 0;
    current_flow = 0.0f;

    // --- Inizializzazione Pin Motore ---
    pinMode(PWM_OUT, OUTPUT);
    pinMode(GPIO_OUT_1, OUTPUT); // EN
    pinMode(GPIO_OUT_2, OUTPUT); // DIR
    
    // --- Inizializzazione Pin Emergenza ---
    pinMode(GPIO_IRQ_1, INPUT_PULLUP);
    pinMode(GPIO_IRQ_2, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(GPIO_IRQ_1), onEmergencyStop, FALLING);
    attachInterrupt(digitalPinToInterrupt(GPIO_IRQ_2), onEmergencyStop, FALLING);

    // --- Inizializzazione Pin Encoder ---
    pinMode(ENC_A, INPUT); 
    pinMode(ENC_B, INPUT);
    pinMode(ENC_Z, INPUT_PULLDOWN); // Pin Z (Index). Se il tuo encoder è attivo basso, usa INPUT_PULLUP
    
    attachInterrupt(digitalPinToInterrupt(ENC_A), onEncoderISR, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENC_B), onEncoderISR, CHANGE);

    setMotor(0, false, false);

    // --- Inizializzazione BLE ---
    BLEDevice::init("Polmone"); 
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());

    BLEService *pService = pServer->createService(HM10_SERVICE_UUID);
    pTxCharacteristic = pService->createCharacteristic(
                      HM10_UART_CHAR_UUID,
                      BLECharacteristic::PROPERTY_NOTIFY |
                      BLECharacteristic::PROPERTY_WRITE  |
                      BLECharacteristic::PROPERTY_WRITE_NR
                    );

    pTxCharacteristic->setCallbacks(new MyCallbacks());
    pTxCharacteristic->addDescriptor(new BLE2902());
    pService->start();
    pServer->getAdvertising()->start();
    Serial.println("BLE Inizializzato [Polmone]. In attesa di accoppiamento...");

    // --- Inizializzazione EEPROM ---
    EEPROM_SPI_Init();
    delay(100);

    Serial.print("Contenuto EEPROM: ");
    Serial.println(read_EEPROM());

    // --- Inizializzazione I2C e Sensori ---
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000);

    Serial.println("\n--- Scansione Sensore in Corso... ---");
    sensoreAttivo = rilevaSensore();

    if (sensoreAttivo == SDP810) {
        Serial.println("Rilevato: SDP810. Avvio modalità continua...");
        Wire.beginTransmission(SDP_ADDR);
        Wire.write(0x36); Wire.write(0x15);
        Wire.endTransmission();
    }
    else if (sensoreAttivo == SFM3300) {
        Serial.println("Rilevato: SFM3300.");
    }
    else {
        Serial.println("ERRORE: Nessun sensore trovato!");
    }

    // --- Timer a 200Hz ---
    timer200Hz = timerBegin(1000000); 
    timerAttachInterrupt(timer200Hz, &onTimer200Hz);
    timerAlarm(timer200Hz, 5000, true, 0); // 5000 µs = 200 Hz

    ultimo_tempo_stampa_ms = millis();
    prev_time_pid = millis();
}

/* ══════════════════════════════════════════════════════════════
 * LOOP
 * ══════════════════════════════════════════════════════════════ */
void loop()
{
    unsigned long tempo_attuale_ms = millis();
    static int tempo = 0;

    /* ── 1. LETTURA SERIALE UART E PONTE ──────────────────────── */
    while (Serial.available() > 0) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (stringaRicevuta.length() > 0) {
                send_BLE(stringaRicevuta);
                stringaRicevuta = "";
            }
        } else {
            if (stringaRicevuta.length() < (EEPROM_TOTAL_SIZE - 1))
                stringaRicevuta += c;
        }
    }

    /* ── 2. STAMPA CONTATORE OGNI 1 SECONDO ──────────────────── */
    if (tempo_attuale_ms - ultimo_tempo_stampa_ms >= INTERVALLO_STAMPA_MS) {
        Serial.print("Tempo: ");
        Serial.print(tempo);
        Serial.print(" | Posizione Encoder: ");
        Serial.println(encoder_pos);
        
        send_BLE(String("Tempo: ") + tempo + String(" Stato: ") + (int)stato + String(" Enc: ") + encoder_pos);
        tempo++;
        ultimo_tempo_stampa_ms = tempo_attuale_ms;
        if(tempo%10==0 || true){
                
        }
        
    }

    /* ── 3. CAMPIONAMENTO E GESTIONE PID (200 Hz) ────────────── */
    if (campiona) {
        campiona = false;
        
        // --- LETTURA E AZZERAMENTO ENCODER ---
        // Se il pin Z va alto, azzera la posizione (Home automatico ad ogni giro)
        if (digitalRead(ENC_Z) == HIGH) {
            encoder_pos = 0;
        }
        
        // Salvataggio sicuro della posizione in locale
        long posizione_corrente = encoder_pos;

        // --- ACQUISIZIONE SENSORE E PID ---
        float valoreletto = NAN;

        if (sensoreAttivo == SDP810) {
            valoreletto = leggi_SDP810();
            if (!isnan(valoreletto)) {
                current_flow = valoreletto * resistenza; 
            }
        }
        else if (sensoreAttivo == SFM3300) {
            valoreletto = leggi_SFM3300();
            if (!isnan(valoreletto)) {
               current_flow = valoreletto; 
            }
        }

        if (!isnan(valoreletto) && (stato == MODE_LINEAR || stato == MODE_SINUSOIDAL)) {
            unsigned long current_time = millis();
            float dt = (current_time - prev_time_pid) / 1000.0f;
            
            if (dt <= 0.0f) dt = 0.005f; 
            prev_time_pid = current_time;

            float setpoint = 0.0f;

            if (stato == MODE_LINEAR) {
                setpoint = target_flow;
            } 
            else if (stato == MODE_SINUSOIDAL) {
                float t = (current_time - start_time_mode1) / 1000.0f;
                setpoint = sine_amplitude * sin(2.0 * M_PI * sine_frequency * t);
            }

            float error = setpoint - current_flow;
            integral += error * dt;
            
            if (integral > 200.0f) integral = 200.0f;
            if (integral < -200.0f) integral = -200.0f;

            float derivative = (error - prev_error) / dt;
            float output = (Kp * error) + (Ki * integral) + (Kd * derivative);
            prev_error = error;

            bool forward = (output >= 0);
            float motor_speed = fabs(output); 
            
            if (motor_speed > 255.0f) motor_speed = 255.0f;

            setMotor(motor_speed, forward, true);
        }

        send_BLE(String("SNSR ")+current_flow+" "+encoder_pos+ " "+ pwmValue);
        //FINE IF SCANNING
    }
}
// FINE CAMPIONAMENTO

/* ══════════════════════════════════════════════════════════════
 * CONTROLLO MOTORE
 * ══════════════════════════════════════════════════════════════ */
void setMotor(float speed, bool dir, bool enable) {
    if (stato == MODE_IDLE) {
        enable = false;
        speed = 0.0f;
    }

    digitalWrite(GPIO_OUT_1, enable ? HIGH : LOW);
    digitalWrite(GPIO_OUT_2, dir ? HIGH : LOW);

    if (!enable) {
        analogWrite(PWM_OUT, 0);
        return;
    }

    float normalized_speed = 0.0f;
    if (speed <= 1.0f && speed >= 0.0f) {
        normalized_speed = speed; 
    } else {
        normalized_speed = speed / 255.0f; 
    }

    if (normalized_speed > 1.0f) normalized_speed = 1.0f;
    if (normalized_speed < 0.0f) normalized_speed = 0.0f;

    int minPWM = 26;  // ~10% di 255
    int maxPWM = 230; // ~90% di 255

    pwmValue = minPWM + (int)(normalized_speed * (maxPWM - minPWM));

    analogWrite(PWM_OUT, pwmValue);
}

/* ══════════════════════════════════════════════════════════════
 * FUNZIONE INVIO MESSAGGI BLE
 * ══════════════════════════════════════════════════════════════ */
void send_BLE(const String& messaggio) {
    if (deviceConnected && pTxCharacteristic != NULL) {
        String payload = messaggio + "\r\n";
        pTxCharacteristic->setValue(payload.c_str());
        pTxCharacteristic->notify();
    }
}

/* ══════════════════════════════════════════════════════════════
 * PARSER COMANDI RICEVUTI
 * ══════════════════════════════════════════════════════════════ */
void parser() {
    int statoLetto = -1;
    float r_parz = 0.0f;
    const char* parsed = msg_BLE.c_str();

    if (sscanf(parsed,"STOP")==1){
        stato = MODE_IDLE;
        Serial.printf("STOP eseguito\n");
        send_BLE(String("STOP eseguito"));
    }
    if (sscanf(parsed, "R : %f", &r_parz) == 1){
        resistenza = r_parz;
        Serial.printf("Nuova resistenza impostata: %.3f\n", resistenza);
        return; 
    }

    if (sscanf(parsed, "Mode %d", &statoLetto) == 1) {
        stato = (Modalita)statoLetto;

        switch (statoLetto) {
        case 0:
            if (sscanf(parsed, "Mode 0 %f", &target_flow) == 1) {
                integral = 0.0f;
                prev_error = 0.0f;
                prev_time_pid = millis();
                Serial.printf("Avviato PID Lineare. Target: %.2f L/s\n", target_flow);
            }
            break;

        case 1:
            if (sscanf(parsed, "Mode 1 %f %f", &sine_amplitude, &sine_frequency) == 2) {
                integral = 0.0f;
                prev_error = 0.0f;
                start_time_mode1 = millis();
                prev_time_pid = start_time_mode1;
                Serial.printf("Avviato PID Sinusoide. Amp: %.2f, Freq: %.2f Hz\n", sine_amplitude, sine_frequency);
            }
            break;

        case 2: 
            if (parametri_int[0] == 1) {
                setMotor(1.0f, true, true);
            } else {
                setMotor(parametri_float[0] / 1000.0f, false, true);
            }
            break;

        case 5:        
            setMotor(0, false, false);
            break;

        case 6: // RESET MANUALE ENCODER (da BLE inviare "Mode 6")
            encoder_pos = 0;
            Serial.println("Encoder azzerato via BLE");
            send_BLE("Encoder azzerato");
            break;
            
        case 512: // EEPROM WRITE
            {
                char auxStr[64] = {0}; 
                if (sscanf(parsed, "Mode 512 %63s", auxStr) == 1) {
                    write_EEPROM(auxStr);
                }
            }
            break;
            
        case 513: // EEPROM READ
            { char* letto = read_EEPROM(); }
            break;
            
        case 514: // SDP_READLOOP
            SFM3300_Start();
            read_SDP810 = true;
            break;
            
        case 515: // SDP_WRITE_LOOP
            read_SDP810 = false;
            SFM3300_Stop();
            break;
            
        case 516:
            send_BLE(String("TROVATO: ") + rilevaSensore());
            break;
        case 517: //scrittura motore
            setMotor(60.0f, true, true);
            break;
        default:
            break;
        }
    }
}

/* ══════════════════════════════════════════════════════════════
 * FUNZIONI PERIFERICHE ORIGINALI (I2C ed EEPROM SPI)
 * ══════════════════════════════════════════════════════════════ */
TipoSensore rilevaSensore() {
    int trovati = 0;
    for (byte addr = 0x01; addr < 0x7F; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) trovati++;
    }
    Wire.beginTransmission(SDP_ADDR);
    if (Wire.endTransmission() == 0) return SDP810;
    Wire.beginTransmission(SFM_ADDR);
    Wire.write(0x10); Wire.write(0x00);
    if (Wire.endTransmission() == 0) {
        delay(100);
        Wire.requestFrom(SFM_ADDR, 3);
        while (Wire.available()) Wire.read();
        return SFM3300;
    }
    return NESSUNO;
}

float leggi_SDP810() {
    Wire.requestFrom(SDP_ADDR, 3);
    if (Wire.available() >= 3) {
        int16_t raw = (Wire.read() << 8) | Wire.read();
        Wire.read(); 
        return (float)raw / SDP_SCALE_FACTOR;
    }
    return NAN;
}

float leggi_SFM3300() {
    Wire.requestFrom(SFM_ADDR, 3);
    if (Wire.available() >= 3) {
        uint16_t raw = (Wire.read() << 8) | Wire.read();
        Wire.read(); 
        return (float)((int32_t)raw - SFM_OFFSET) / SFM_SCALE_FACTOR;
    }
    return NAN;
}

void EEPROM_SPI_Init() {
    pinMode(PIN_CS, OUTPUT);
    CS_High();
    vspi.begin(18, 19, 23, PIN_CS);
}

static void EEPROM_WaitReady() {
    uint8_t status;
    do {
        vspi.beginTransaction(eepromSettings);
        CS_Low(); vspi.transfer(EEPROM_RDSR); status = vspi.transfer(0x00); CS_High();
        vspi.endTransaction();
        delayMicroseconds(100);
    } while (status & 0x01);
}

static void EEPROM_WriteEnable() {
    vspi.beginTransaction(eepromSettings);
    CS_Low(); vspi.transfer(EEPROM_WREN); CS_High();
    vspi.endTransaction();
}

void write_EEPROM(const char* str) {
    for (uint16_t addr = 0; addr < EEPROM_TOTAL_SIZE; addr += EEPROM_PAGE_SIZE) {
        EEPROM_WriteEnable();
        vspi.beginTransaction(eepromSettings);
        CS_Low(); vspi.transfer(EEPROM_WRITE);
        vspi.transfer((addr >> 8) & 0xFF); vspi.transfer(addr & 0xFF);
        for (int i = 0; i < EEPROM_PAGE_SIZE; i++) vspi.transfer(0xFF);
        CS_High();
        vspi.endTransaction();
        EEPROM_WaitReady();
    }
    uint16_t bytes_left = (uint16_t)strlen(str) + 1;
    uint16_t src_offset = 0;
    uint16_t addr = 0x0000;
    while (bytes_left > 0) {
        uint16_t chunk = (bytes_left < EEPROM_PAGE_SIZE) ? bytes_left : EEPROM_PAGE_SIZE;
        EEPROM_WriteEnable();
        vspi.beginTransaction(eepromSettings);
        CS_Low(); vspi.transfer(EEPROM_WRITE);
        vspi.transfer((addr >> 8) & 0xFF); vspi.transfer(addr & 0xFF);
        for (uint16_t i = 0; i < chunk; i++) vspi.transfer((uint8_t)str[src_offset + i]);
        CS_High();
        vspi.endTransaction();
        EEPROM_WaitReady();
        addr += chunk; src_offset += chunk; bytes_left -= chunk;
    }
}

char* read_EEPROM() {
    static char result[EEPROM_TOTAL_SIZE];
    vspi.beginTransaction(eepromSettings);
    CS_Low(); vspi.transfer(EEPROM_READ); vspi.transfer(0x00); vspi.transfer(0x00);
    for (uint16_t i = 0; i < EEPROM_TOTAL_SIZE; i++) {
        result[i] = (char)vspi.transfer(0x00);
        if (result[i] == '\0') break;
    }
    CS_High(); vspi.endTransaction();
    result[EEPROM_TOTAL_SIZE - 1] = '\0';
    return result;
}