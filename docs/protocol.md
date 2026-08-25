# Communication protocol notes

This document summarizes the communication path used by the final ESP32 system.

## ESP32 system

- Device name: `Polmone`
- Service: `0000FFE0-0000-1000-8000-00805F9B34FB`
- Characteristic: `0000FFE1-0000-1000-8000-00805F9B34FB`
- Telemetry frame: `SNSR <flow> <encoder_position> <pwm>`
- Serial monitor baud rate: `115200`

The main GUI sends commands through the same HM-10 characteristic and parses the `SNSR` telemetry frame. The resistance command uses the firmware syntax `R : <value>`.

## Previous bridge architecture

- Service family: Nordic UART Service
- UART baud rate in code: `57600`
- A bridge comment mentions `9600`; the code and comment must be reconciled.

## Development history

The repository also contains earlier GUI and firmware variants using Nordic UART identifiers, different device names, comma-separated telemetry and other baud rates. They are retained under [archive](../archive/) as development history and are not part of the primary ESP32 control path.
