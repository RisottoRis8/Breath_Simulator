
#ifndef BLE_MANAGER_H
#define BLE_MANAGER_H

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "Config.h"
#include "MotorController.h"
#include "EepromManager.h"
#include "SensorManager.h"

class BleManager {
public:
    BleManager();
    void begin(MotorController& motor, EepromManager& eeprom, SensorManager& sensors, volatile Modalita& stato, float& resistenza);
    void inviaTesto(const String& messaggio);
    void inviaDatiSensoreDecimati(float current_flow, long encoder_pos, int pwm_value);
    void processaCarattere(char c);

    // Setter di stato interni per le Callback asincrone
    void setDeviceConnected(bool connected) { deviceConnected = connected; }

private:
    BLEServer *pServer;
    BLECharacteristic *pTxCharacteristic;
    bool deviceConnected;
    String msg_BLE;

    // Riferimenti ai moduli di sistema gestiti dal parser
    MotorController* _motor;
    EepromManager* _eeprom;
    SensorManager* _sensors;
    volatile Modalita* _pStato;
    float* _pResistenza;

    void eseguiParser();
};

#endif