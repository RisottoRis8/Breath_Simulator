
#include "Config.h"
#include "EepromManager.h"
#include "SensorManager.h"
#include "MotorController.h"
#include "BleManager.h"

// ── Istanziazione degli Oggetti Modulari ──────────────────────────
EepromManager eeprom;
SensorManager sensori;
MotorController motore;
BleManager ble;

// ── Stati Condivisi Necessari per il Coordinamento ────────────────
volatile Modalita stato = MODE_IDLE;
float resistenza = 1.0f;
float current_flow = 0.0f;

// Timers hardware
hw_timer_t* timer200Hz = nullptr;
volatile bool campiona = false;
unsigned long ultimo_tempo_stampa_ms = 0;
String stringaRicevuta = "";

// ── Wrapper ISR di Aggancio Hardware ──────────────────────────────
void IRAM_ATTR onTimer200Hz() {
    campiona = true;
}

void IRAM_ATTR onEncoderISR() {
    motore.encoderTick();
}

void IRAM_ATTR onEmergencyStopISR() {
    motore.handleEmergencyStop(stato);
}

/* ══════════════════════════════════════════════════════════════
 * SETUP
 * ══════════════════════════════════════════════════════════════ */
void setup() {
    Serial.begin(115200);
    while (!Serial) { delay(10); }
    delay(1000);

    // Inizializza i moduli indipendenti
    motore.begin();
    eeprom.begin();
    sensori.begin();
    ble.begin(motore, eeprom, sensori, stato, resistenza);

    // Stampa stato iniziale EEPROM
    Serial.print("Contenuto EEPROM: ");
    Serial.println(eeprom.read());

    // Collegamento degli Interrupt ai wrapper ISR
    attachInterrupt(digitalPinToInterrupt(GPIO_IRQ_1), onEmergencyStopISR, FALLING);
    attachInterrupt(digitalPinToInterrupt(GPIO_IRQ_2), onEmergencyStopISR, FALLING);
    attachInterrupt(digitalPinToInterrupt(ENC_A), onEncoderISR, CHANGE);
    attachInterrupt(digitalPinToInterrupt(ENC_B), onEncoderISR, CHANGE);

    // Avvio del timer di campionamento a 200Hz
    timer200Hz = timerBegin(1000000); 
    timerAttachInterrupt(timer200Hz, &onTimer200Hz);
    timerAlarm(timer200Hz, 5000, true, 0); // 5000 µs = 200 Hz

    ultimo_tempo_stampa_ms = millis();
}

/* ══════════════════════════════════════════════════════════════
 * LOOP PRINCIPALE
 * ══════════════════════════════════════════════════════════════ */
void loop() {
    unsigned long tempo_attuale_ms = millis();
    static int contatore_secondi = 0;

    // 1. Lettura Seriale Hard-Bridge (Seriale PC -> BLE)
    while (Serial.available() > 0) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (stringaRicevuta.length() > 0) {
                ble.inviaTesto(stringaRicevuta);
                stringaRicevuta = "";
            }
        } else {
            if (stringaRicevuta.length() < (EEPROM_TOTAL_SIZE - 1)) {
                stringaRicevuta += c;
            }
        }
    }

    // 2. Report di Stato su seriale ogni 1 secondo
    if (tempo_attuale_ms - ultimo_tempo_stampa_ms >= 1000) {
        ultimo_tempo_stampa_ms = tempo_attuale_ms;
        Serial.printf("Tempo: %d | Stato: %d | Enc: %ld\n", contatore_secondi, (int)stato, motore.getEncoderPos());
        contatore_secondi++;
    }

    // 3. Elaborazione della coda di campionamento a 200 Hz
    if (campiona) {
        campiona = false;

        // Azzeramento index su Pin Z (Se attivo alto)
        if (digitalRead(ENC_Z) == HIGH) {
            motore.azzeraEncoder();
        }

        // Acquisizione flusso e aggiornamento anello PID
        float valoreFlusso = sensori.leggiFlusso(resistenza);
        if (!isnan(valoreFlusso)) {
            current_flow = valoreFlusso;
        }

        motore.updatePID(current_flow, stato);
        motore.controllaInversioneSwing(stato); // Logica invertitore per Mode 520

        // Trasmissione dati asincrona verso l'applicazione (GUI) decimata a 20Hz
        ble.inviaDatiSensoreDecimati(current_flow, motore.getEncoderPos(), motore.getPwmValue());
    }
}