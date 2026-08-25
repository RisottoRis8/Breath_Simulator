
#include "BleManager.h"

// Classi di Callback locali per disaccoppiare lo Stack BLE
class ServerCallbacks : public BLEServerCallbacks {
    BleManager* _mgr;
public:
    ServerCallbacks(BleManager* mgr) : _mgr(mgr) {}
    void onConnect(BLEServer* pServer) override { _mgr->setDeviceConnected(true); }
    void onDisconnect(BLEServer* pServer) override {
        _mgr->setDeviceConnected(false);
        pServer->startAdvertising(); 
    }
};

class CharacteristicCallbacks : public BLECharacteristicCallbacks {
    BleManager* _mgr;
public:
    CharacteristicCallbacks(BleManager* mgr) : _mgr(mgr) {}
    void onWrite(BLECharacteristic *pCharacteristic) override {
        String rxValue = pCharacteristic->getValue();
        if (rxValue.length() > 0) {
            for (int i = 0; i < rxValue.length(); i++) {
                _mgr->processaCarattere(rxValue[i]);
            }
        }
    }
};

BleManager::BleManager() : pServer(nullptr), pTxCharacteristic(nullptr), deviceConnected(false), msg_BLE(""),
                           _motor(nullptr), _eeprom(nullptr), _sensors(nullptr), _pStato(nullptr), _pResistenza(nullptr) {}

void BleManager::begin(MotorController& motor, EepromManager& eeprom, SensorManager& sensors, volatile Modalita& stato, float& resistenza) {
    _motor = &motor; _eeprom = &eeprom; _sensors = &sensors; _pStato = &stato; _pResistenza = &resistenza;

    BLEDevice::init("Polmone");
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks(this));

    BLEService *pService = pServer->createService(HM10_SERVICE_UUID);
    pTxCharacteristic = pService->createCharacteristic(
        HM10_UART_CHAR_UUID,
        BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
    );

    pTxCharacteristic->setCallbacks(new CharacteristicCallbacks(this));
    pTxCharacteristic->addDescriptor(new BLE2902());
    pService->start();
    pServer->getAdvertising()->start();
}

void BleManager::inviaTesto(const String& messaggio) {
    if (deviceConnected && pTxCharacteristic != nullptr) {
        String payload = messaggio + "\r\n";
        pTxCharacteristic->setValue(payload.c_str());
        pTxCharacteristic->notify();
    }
}

void BleManager::inviaDatiSensoreDecimati(float current_flow, long encoder_pos, int pwm_value) {
    static int contatore_ble = 0;
    contatore_ble++;

    if (contatore_ble >= 10) { // Riduzione da 200Hz a 20Hz
        contatore_ble = 0;
        if (deviceConnected && pTxCharacteristic != nullptr) {
            char msg_buf[64];
            snprintf(msg_buf, sizeof(msg_buf), "SNSR %.3f %ld %d\r\n", current_flow, encoder_pos, pwm_value);
            pTxCharacteristic->setValue((uint8_t*)msg_buf, strlen(msg_buf));
            pTxCharacteristic->notify();
        }
    }
}

void BleManager::processaCarattere(char c) {
    if (c == '\n' || c == '\r') {
        if (msg_BLE.length() > 0) {
            eseguiParser();
            msg_BLE = "";
        }
    } else {
        msg_BLE += c;
    }
}

void BleManager::eseguiParser() {
    int statoLetto = -1;
    float r_parz = 0.0f;
    const char* parsed = msg_BLE.c_str();

    if (sscanf(parsed, "STOP") == 1) {
        *_pStato = MODE_IDLE;
        _motor->setMotor(0, false, false, *_pStato);
        inviaTesto("STOP eseguito");
        return;
    }
    if (sscanf(parsed, "R : %f", &r_parz) == 1) {
        *_pResistenza = r_parz;
        return;
    }

    if (sscanf(parsed, "Mode %d", &statoLetto) == 1) {
        *_pStato = (Modalita)statoLetto;
        float p1 = 0.0f, p2 = 0.0f;

        switch (statoLetto) {
            case 0:
                if (sscanf(parsed, "Mode 0 %f", &p1) == 1) _motor->setTargetFlow(p1);
                break;
            case 1:
                if (sscanf(parsed, "Mode 1 %f %f", &p1, &p2) == 2) _motor->setSineParams(p1, p2);
                break;
            case 5:
                _motor->setMotor(0, false, false, *_pStato);
                break;
            case 6:
                _motor->azzeraEncoder();
                inviaTesto("Encoder azzerato");
                break;
            case 512: {
                char auxStr[64] = {0};
                if (sscanf(parsed, "Mode 512 %63s", auxStr) == 1) _eeprom->write(auxStr);
                break;
            }
            case 513:
                _eeprom->read();
                break;
            case 516:
                inviaTesto(String("TROVATO: ") + _sensors->getSensoreAttivo());
                break;
            case 517:
                _motor->setMotor(60.0f, true, true, *_pStato);
                break;
            case 520: // Avvia Ping Pong
                if (sscanf(parsed, "Mode 520 %f", &p1) == 1) {
                    _motor->avviaSwing(p1);
                    _motor->setMotor(p1, true, true, *_pStato);
                    inviaTesto("Debug Swing Avviato");
                }
                break;
            case 521: // Ferma Ping Pong
                *_pStato = MODE_IDLE;
                _motor->setMotor(0, false, false, *_pStato);
                inviaTesto("Debug Swing Fermato");
                break;
            default:
                break;
        }
    }
}