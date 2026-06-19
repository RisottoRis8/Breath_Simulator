#include <Wire.h>
#include <SPI.h>

// Indirizzi I2C dei due sensori
#define SDP_ADDR  0x25 
#define SFM_ADDR  0x40 

// Pin I2C ESP32
#define I2C_SDA 21
#define I2C_SCL 22

// SPI Cs
#define PIN_CS    5
 // COMANDI SPI
#define EEPROM_WREN   0x06
#define EEPROM_RDSR   0x05
#define EEPROM_WRITE  0x02
#define EEPROM_READ   0x03

#define EEPROM_PAGE_SIZE   64
#define EEPROM_TOTAL_SIZE  32768

/* ── SPI settings ───────────────────────────────────────────── */
SPIClass vspi(VSPI);
SPISettings eepromSettings(1000000, MSBFIRST, SPI_MODE0);

/* ── CS helpers ─────────────────────────────────────────────── */
static inline void CS_Low()  { digitalWrite(PIN_CS, LOW);  }
static inline void CS_High() { digitalWrite(PIN_CS, HIGH); }

// Costanti di conversione
const float SDP_SCALE_FACTOR = 60.0;  // Per SDP810 (Pa)
const float SFM_SCALE_FACTOR = 120.0;  // Per SFM3300 (slm - standard liters per minute)
const int16_t SFM_OFFSET = 32768;      // Offset fisso dell'SFM3300

// Tipo di sensore rilevato
enum TipoSensore { NESSUNO, SDP810, SFM3300 };
TipoSensore sensoreAttivo = SDP810;

// Variabili per l'interrupt a 200Hz (5000 us)
const unsigned long INTERVALLO_US = 5000; 
unsigned long ultimo_tempo_us = 0;

// Variabili per la gestione del timer di stampa EEPROM (2 secondi)
unsigned long ultimo_tempo_stampa_ms = 0;
const unsigned long INTERVALLO_STAMPA_MS = 2000;

// Buffer per la lettura della stringa da seriale
String stringaRicevuta = "";

// Dichiarazione funzioni
TipoSensore rilevaSensore();
float leggi_SDP810();
float leggi_SFM3300();
void EEPROM_SPI_Init();
void write_EEPROM(const char* str);
char* read_EEPROM();

void setup() {
  Serial.begin(460800);
  while (!Serial) { delay(10); }
  EEPROM_SPI_Init();

  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000); // 400 kHz Fast Mode

  Serial.println("\n--- Scansione Sensore in Corso... ---");
  sensoreAttivo = rilevaSensore();

  // Inizializzazione specifica in base al sensore trovato
  if (sensoreAttivo == SDP810) {
    Serial.println("Rilevato: SDP810. Avvio modalità continua...");
    Wire.beginTransmission(SDP_ADDR);
    Wire.write(0x36); Wire.write(0x15); // Comando misura continua SDP
    Wire.endTransmission();
  } 
  else if (sensoreAttivo == SFM3300) {
    Serial.println("Rilevato: SFM3300. Avvio modalità continua...");
    Wire.beginTransmission(SFM_ADDR);
    Wire.write(0x10); Wire.write(0x00); // Comando misura continua SFM
    Wire.endTransmission();
    delay(100); // L'SFM3300 richiede un piccolo reset temporale all'avvio
  } 
  else {
    Serial.println("ERRORE: Nessun sensore compatibile trovato sul bus I2C!");
    while (1); // Blocco di sicurezza
  }

  Serial.print("Contenuto iniziale EEPROM: ");
  Serial.println(read_EEPROM());
  
  ultimo_tempo_us = micros();
  ultimo_tempo_stampa_ms = millis();
}

void loop() {
  unsigned long tempo_attuale_us = micros();
  unsigned long tempo_attuale_ms = millis();

  /* ── 1. LETTURA SERIALE (NON BLOCCANTE) ────────────────────── */
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (stringaRicevuta.length() > 0) {
        Serial.print("\n[EEPROM] Scrittura nuova stringa: ");
        Serial.println(stringaRicevuta);
        
        // Salviamo in EEPROM (aggiungendo il terminatore di stringa)
        write_EEPROM(stringaRicevuta.c_str());
        
        stringaRicevuta = ""; // Svuota il buffer per la prossima stringa
      }
    } else {
      // Evita overflow del buffer della EEPROM
      if (stringaRicevuta.length() < (EEPROM_TOTAL_SIZE - 1)) {
        stringaRicevuta += c;
      }
    }
  }

  /* ── 2. STAMPA CONTENUTO EEPROM OGNI 2 SECONDI ────────────── */
  if (tempo_attuale_ms - ultimo_tempo_stampa_ms >= INTERVALLO_STAMPA_MS) {
    ultimo_tempo_stampa_ms = tempo_attuale_ms;
    Serial.print("[EEPROM Lettura]: ");
    Serial.println(read_EEPROM());
  }

  /* ── 3. CAMPIONAMENTO SENSORI A 200Hz ──────────────────────── */
  if (tempo_attuale_us - ultimo_tempo_us >= INTERVALLO_US) {
    ultimo_tempo_us += INTERVALLO_US;

    float valoreletto = NAN;

    if (sensoreAttivo == SDP810) {
      valoreletto = leggi_SDP810();
      if (!isnan(valoreletto)) {
        Serial.print("SDP_Pa:"); Serial.println(valoreletto, 2);
      }
    } 
    else if (sensoreAttivo == SFM3300) {
      valoreletto = leggi_SFM3300();
      if (!isnan(valoreletto)) {
        Serial.print("SFM_slm:"); Serial.println(valoreletto, 2);
      }
    }
  }
}

// ========================================================
// FUNZIONE DI RILEVAMENTO AUTOMATICO (I2C SCANNER)
// ========================================================
TipoSensore rilevaSensore() {
  Wire.beginTransmission(SDP_ADDR);
  if (Wire.endTransmission() == 0) return SDP810;

  Wire.beginTransmission(SFM_ADDR);
  if (Wire.endTransmission() == 0) return SFM3300;

  return NESSUNO;
}

// ========================================================
// LETTURA SDP810 (Ritorna Pascal)
// ========================================================
float leggi_SDP810() {
  Wire.requestFrom(SDP_ADDR, 3);
  if (Wire.available() >= 3) {
    int16_t raw = (Wire.read() << 8) | Wire.read();
    Wire.read(); // Salta CRC
    return (float)raw / SDP_SCALE_FACTOR;
  }
  return NAN;
}

// ========================================================
// LETTURA SFM3300 (Ritorna Litri al Minuto - slm)
// ========================================================
float leggi_SFM3300() {
  Wire.requestFrom(SFM_ADDR, 3);
  if (Wire.available() >= 3) {
    uint16_t raw = (Wire.read() << 8) | Wire.read();
    Wire.read(); // Salta CRC
    return (float)((int32_t)raw - SFM_OFFSET) / SFM_SCALE_FACTOR;
  }
  return NAN;
}

void EEPROM_SPI_Init() {
    pinMode(PIN_CS, OUTPUT);
    CS_High();
    vspi.begin(18, 19, 23, PIN_CS);   // SCK, MISO, MOSI, SS
}

static void EEPROM_WaitReady() {
    uint8_t status;
    do {
        vspi.beginTransaction(eepromSettings);
        CS_Low();
        vspi.transfer(EEPROM_RDSR);
        status = vspi.transfer(0x00);
        CS_High();
        vspi.endTransaction();
        delayMicroseconds(100);
    } while (status & 0x01);
}

static void EEPROM_WriteEnable() {
    vspi.beginTransaction(eepromSettings);
    CS_Low();
    vspi.transfer(EEPROM_WREN);
    CS_High();
    vspi.endTransaction();
}

/* ══════════════════════════════════════════════════════════════
 * write_EEPROM (OTTIMIZZATA: Cancella solo quello che serve)
 * ══════════════════════════════════════════════════════════════ */
void write_EEPROM(const char* str) {
    uint16_t bytes_to_write = (uint16_t)strlen(str) + 1;
    
    // Per sicurezza stringa non oltre i limiti fisici
    if (bytes_to_write > EEPROM_TOTAL_SIZE) bytes_to_write = EEPROM_TOTAL_SIZE;

    uint16_t src_offset = 0;
    uint16_t addr       = 0x0000;

    while (bytes_to_write > 0) {
        uint16_t chunk = (bytes_to_write < EEPROM_PAGE_SIZE) ? bytes_to_write : EEPROM_PAGE_SIZE;

        // Nota: Supponendo che la tua EEPROM supporti la sovrascrittura di pagina 
        // o che i byte non scritti rimangano intatti.
        EEPROM_WriteEnable();

        vspi.beginTransaction(eepromSettings);
        CS_Low();
        vspi.transfer(EEPROM_WRITE);
        vspi.transfer((addr >> 8) & 0xFF);
        vspi.transfer( addr       & 0xFF);
        
        for (uint16_t i = 0; i < chunk; i++) {
            vspi.transfer((uint8_t)str[src_offset + i]);
        }
        
        // Se la pagina non è riempita dal chunk, la completiamo con il terminatore o 0xFF
        // per evitare sporcizia sulla stringa precedente
        if (chunk < EEPROM_PAGE_SIZE && src_offset + chunk == strlen(str) + 1) {
             for (uint16_t i = chunk; i < EEPROM_PAGE_SIZE; i++) {
                 vspi.transfer(0x00); 
             }
             bytes_to_write = chunk; // Forza l'uscita al prossimo ciclo
        }

        CS_High();
        vspi.endTransaction();
        EEPROM_WaitReady();

        addr       += EEPROM_PAGE_SIZE;
        src_offset += chunk;
        bytes_to_write -= chunk;
    }
}

/* ══════════════════════════════════════════════════════════════
 * read_EEPROM
 * ══════════════════════════════════════════════════════════════ */
char* read_EEPROM() {
    static char result[EEPROM_TOTAL_SIZE];

    vspi.beginTransaction(eepromSettings);
    CS_Low();
    vspi.transfer(EEPROM_READ);
    vspi.transfer(0x00);
    vspi.transfer(0x00);

    for (uint16_t i = 0; i < EEPROM_TOTAL_SIZE; i++) {
        result[i] = (char)vspi.transfer(0x00);
        if (result[i] == '\0') break;
    }

    CS_High();
    vspi.endTransaction();

    result[EEPROM_TOTAL_SIZE - 1] = '\0';
    return result;
}