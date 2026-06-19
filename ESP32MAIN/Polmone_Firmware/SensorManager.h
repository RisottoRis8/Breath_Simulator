
#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

#include <Wire.h>
#include "Config.h"

class SensorManager {
public:
    SensorManager();
    void begin();
    TipoSensore rilevaSensore();
    float leggiFlusso(float resistenza);
    TipoSensore getSensoreAttivo() const { return sensoreAttivo; }

private:
    TipoSensore sensoreAttivo;
    float leggi_SDP810();
    float leggi_SFM3300();
};

#endif