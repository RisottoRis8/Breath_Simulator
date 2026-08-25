#include "EepromManager.h"

EepromManager::EepromManager() : vspi(VSPI), eepromSettings(1000000, MSBFIRST, SPI_MODE0) {}

void EepromManager::begin() {
    pinMode(PIN_CS, OUTPUT);
    CS_High();
    vspi.begin(18, 19, 23, PIN_CS);
}

void EepromManager::waitReady() {
    uint8_t status;
    do {
        vspi.beginTransaction(eepromSettings);
        CS_Low(); vspi.transfer(EEPROM_RDSR); status = vspi.transfer(0x00); CS_High();
        vspi.endTransaction();
        delayMicroseconds(100);
    } while (status & 0x01);
}

void EepromManager::writeEnable() {
    vspi.beginTransaction(eepromSettings);
    CS_Low(); vspi.transfer(EEPROM_WREN); CS_High();
    vspi.endTransaction();
}

void EepromManager::write(const char* str) {
    for (uint16_t addr = 0; addr < EEPROM_TOTAL_SIZE; addr += EEPROM_PAGE_SIZE) {
        writeEnable();
        vspi.beginTransaction(eepromSettings);
        CS_Low(); vspi.transfer(EEPROM_WRITE);
        vspi.transfer((addr >> 8) & 0xFF); vspi.transfer(addr & 0xFF);
        for (int i = 0; i < EEPROM_PAGE_SIZE; i++) vspi.transfer(0xFF);
        CS_High(); vspi.endTransaction();
        waitReady();
    }
    uint16_t bytes_left = (uint16_t)strlen(str) + 1;
    uint16_t src_offset = 0;
    uint16_t addr = 0x0000;
    while (bytes_left > 0) {
        uint16_t chunk = (bytes_left < EEPROM_PAGE_SIZE) ? bytes_left : EEPROM_PAGE_SIZE;
        writeEnable();
        vspi.beginTransaction(eepromSettings);
        CS_Low(); vspi.transfer(EEPROM_WRITE);
        vspi.transfer((addr >> 8) & 0xFF); vspi.transfer(addr & 0xFF);
        for (uint16_t i = 0; i < chunk; i++) vspi.transfer((uint8_t)str[src_offset + i]);
        CS_High(); vspi.endTransaction();
        waitReady();
        addr += chunk; src_offset += chunk; bytes_left -= chunk;
    }
}

char* EepromManager::read() {
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
