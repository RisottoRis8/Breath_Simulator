
#include "SensorManager.h"

SensorManager::SensorManager() : sensoreAttivo(NESSUNO) {}

void SensorManager::begin() {
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000);
    sensoreAttivo = rilevaSensore();

    if (sensoreAttivo == SDP810) {
        Wire.beginTransmission(SDP_ADDR);
        Wire.write(0x36); Wire.write(0x15);
        Wire.endTransmission();
    }
}

TipoSensore SensorManager::rilevaSensore() {
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

float SensorManager::leggiFlusso(float resistenza) {
    float valoreLetto = NAN;
    if (sensoreAttivo == SDP810) {
        valoreLetto = leggi_SDP810();
        if (!isnan(valoreLetto)) return valoreLetto * resistenza;
    } else if (sensoreAttivo == SFM3300) {
        valoreLetto = leggi_SFM3300();
        if (!isnan(valoreLetto)) return valoreLetto;
    }
    return valoreLetto;
}

float SensorManager::leggi_SDP810() {
    Wire.requestFrom(SDP_ADDR, 3);
    if (Wire.available() >= 3) {
        int16_t raw = (Wire.read() << 8) | Wire.read();
        Wire.read(); 
        return (float)raw / SDP_SCALE_FACTOR;
    }
    return NAN;
}

float SensorManager::leggi_SFM3300() {
    Wire.requestFrom(SFM_ADDR, 3);
    if (Wire.available() >= 3) {
        uint16_t raw = (Wire.read() << 8) | Wire.read();
        Wire.read(); 
        return (float)((int32_t)raw - SFM_OFFSET) / SFM_SCALE_FACTOR;
    }
    return NAN;
}