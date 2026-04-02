# Gruppo Viola, ETBL
---

Simulatore di Polmone basato su siringa

---

## Settimana 1

- Pseudocodice/diagramma logico
- Schematica di collegamento
- Come comunicano i dispositivi
- Componenti usati

---

## Ordine di implementazione

1. Muovere motore manualmente (PWM fisso)
2. Leggere encoder bene
3. Homing con microswitch
4. Controllo posizione (PID)
5. Comando UART POS
6. Sinusoide
7. Pattern

---

## Funzioni richieste

1. Posizione carrello per garantire volume della siringa richiesto (da siringa di 2.46L a tipo 1L)
2. Poter generare flussi costanti in singole corse
3. Sinusoide (avanti e indietro) con ampiezza e frequenza
4. Poter riprodurre tracce “Volume rimasto VS tempo” oppure “flusso vs Tempo”

---

## PCB

- Scheda con: 24V a 5V (buck)
- HC505 come scheda bluetooth
- Led di stato (led su 24V, 5V, 3.3V per power rails)
- Pin non usati a morsettiere ausiliarie, per utilizzo futuro

---

## Da stampare

- Supporto per encoder e BLDC
- Nuovi supporti siringa e microswitch
- Supporto PCB
- Ugello flussimetro e sensore di pressione
