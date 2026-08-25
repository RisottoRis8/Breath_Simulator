
#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

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

// ── Costanti di conversione ───────────────────────────────────────
const float SDP_SCALE_FACTOR = 60.0f;
const float SFM_SCALE_FACTOR = 120.0f;
const int16_t SFM_OFFSET     = 32768;

// ── BLE HM10 Config ───────────────────────────────────────────────
#define HM10_SERVICE_UUID      "0000FFE0-0000-1000-8000-00805F9B34FB"
#define HM10_UART_CHAR_UUID    "0000FFE1-0000-1000-8000-00805F9B34FB"

// ── Tipi e Stati ──────────────────────────────────────────────────
enum TipoSensore { NESSUNO, SDP810, SFM3300 };

enum Modalita {
    MODE_LINEAR = 0,
    MODE_SINUSOIDAL = 1,
    MODE_CALIBRATION = 2,
    MODE_PUSH = 3,
    MODE_HOME = 4,
    MODE_IDLE = 5,
    MODE_DEBUG_SWING = 520,  // Nuova modalità Ping-Pong richiesto
    MODE_DEBUG = 1000
};

#endif