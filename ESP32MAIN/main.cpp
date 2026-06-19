#include <Arduino.h>

// Definiamo un puntatore al timer hardware
hw_timer_t * timer = NULL;

// Questo flag volatile segnala al loop quando è il momento di agire
volatile bool interruptScattato = false;

// Questa è la ISR (Interrupt Service Routine). Deve avere l'attributo ARDUINO_ISR_ATTR
void ARDUINO_ISR_ATTR onTimer() {
  interruptScattato = true; // Azione fulminea: alziamo solo la bandierina
}

void setup() {
  Serial.begin(115200);

  // 1. Inizializza il Timer 0. 
  // L'ESP32 ha un clock di base a 80 MHz. Configurando la frequenza del timer a 1.000.000 Hz (1 MHz),
  // otteniamo una risoluzione di esattamente 1 microsecondo per ogni "tic" del timer.
  timer = timerBegin(1000000); 

  // 2. Associa la funzione 'onTimer' al nostro timer
  timerAttachInterrupt(timer, &onTimer);

  // 3. Imposta l'allarme. 
  // Vogliamo 200Hz -> 1.000.000 / 200 = 5000 microsecondi (quindi 5000 tic).
  // Il terzo argomento 'true' significa che il timer si ricarica automaticamente (loop infinito).
  timerAlarm(timer, 5000, true, 0); 
}

void loop() {
  // Il loop gira alla massima velocità possibile, ma esegue il codice 
  // solo quando l'interrupt dà il via libera
  if (interruptScattato) {
    interruptScattato = false; // Resetta immediatamente il flag

    // --- QUI METTI IL CODICE CHE VUOI TEMPORIZZARE ---
    // Ad esempio la lettura del sensore SDP810 e la stampa seriale.
    // Questo punto è perfettamente temporizzato a 200Hz spaccati.
    
    Serial.println("Lettura eseguita con precisione hardware!");
  }

  // Qui puoi mettere altro codice (es. gestire un display, comandi WiFi).
  // Anche se questo codice impiega 2 o 3 millisecondi, non rovinerà 
  // la precisione dell'interrupt a 200Hz.
}