#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

BLEServer *pServer = NULL;
BLECharacteristic *pTxCharacteristic;
bool deviceConnected = false;

// UUID standard per il servizio Nordic UART (NUS)
#define SERVICE_UUID           "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_RX "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define CHARACTERISTIC_UUID_TX "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
      deviceConnected = true;
      Serial.println("Client BLE Connesso!");
    };
    void onDisconnect(BLEServer* pServer) {
      deviceConnected = false;
      Serial.println("Client BLE Disconnesso. Pubblicità riavviata.");
      // Un piccolo delay aiuta il chip a resettare lo stack BLE correttamente
      delay(500); 
      pServer->getAdvertising()->start(); 
    }
};

class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      // Usiamo String (Arduino) invece di std::string
      String rxValue = pCharacteristic->getValue(); 

      if (rxValue.length() > 0) {
        for (int i = 0; i < rxValue.length(); i++) {
          Serial2.print(rxValue[i]); // Invia allo STM32
        }
        
        // Debug su monitor seriale del PC
        Serial.print("Ricevuto da BLE e inviato a STM32: ");
        Serial.println(rxValue);
      }
    }
};

void setup() {
  Serial.begin(115200);
  
  // Configurazione UART2: Baudrate 9600 (deve coincidere con huart1 dello STM32)
  // Pin 16 (RX), Pin 17 (TX)
  Serial2.begin(9600, SERIAL_8N1, 16, 17); 

  // Inizializzazione BLE
  BLEDevice::init("ESP32_BLE_Bridge");
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());

  // Creazione Servizio UART
  BLEService *pService = pServer->createService(SERVICE_UUID);

  // Caratteristica TX (L'ESP32 invia dati al telefono)
  pTxCharacteristic = pService->createCharacteristic(
                        CHARACTERISTIC_UUID_TX,
                        BLECharacteristic::PROPERTY_NOTIFY
                      );
  pTxCharacteristic->addDescriptor(new BLE2902());

  // Caratteristica RX (L'ESP32 riceve dati dal telefono)
  BLECharacteristic *pRxCharacteristic = pService->createCharacteristic(
                                         CHARACTERISTIC_UUID_RX,
                                         BLECharacteristic::PROPERTY_WRITE
                                       );
  pRxCharacteristic->setCallbacks(new MyCallbacks());

  pService->start();
  
  // Avvio Advertising
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);  
  pAdvertising->setMaxPreferred(0x12);
  BLEDevice::startAdvertising();
  
  Serial.println("BLE Pronto. In attesa di connessione...");
}

void loop() {
    // Se c'è un client connesso e ci sono dati dallo STM32 (UART2)
    if (deviceConnected && Serial2.available()) {
        // Leggiamo la stringa fino al terminatore inviato dallo STM32
        String data = Serial2.readStringUntil('\n'); 
        
        if (data.length() > 0) {
            // Aggiungiamo esplicitamente il fine riga per aiutare la decodifica dell'app client
            data += "\n"; 
            
            // Impostiamo il valore e inviamo la notifica
            pTxCharacteristic->setValue(data.c_str());
            pTxCharacteristic->notify(); 
            
            Serial.print("Inviato a BLE: ");
            Serial.print(data);
        }
    }

    // Piccola pausa per stabilità del sistema ed evitare watchdog reset
    delay(10);
}