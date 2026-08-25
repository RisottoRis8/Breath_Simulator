
#ifndef EEPROM_MANAGER_H
#define EEPROM_MANAGER_H

#include <SPI.h>
#include "Config.h"

class EepromManager {
public:
    EepromManager();
    void begin();
    void write(const char* str);
    char* read();

private:
    SPIClass vspi;
    SPISettings eepromSettings;
    void waitReady();
    void writeEnable();
    static inline void CS_Low()  { digitalWrite(PIN_CS, LOW);  }
    static inline void CS_High() { digitalWrite(PIN_CS, HIGH); }
};

#endif