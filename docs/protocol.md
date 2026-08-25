# Communication protocol notes

This is a verified working note, not yet a final protocol specification.

## ESP32 main candidate

- Device name: `Polmone`
- Service: `0000FFE0-0000-1000-8000-00805F9B34FB`
- Characteristic: `0000FFE1-0000-1000-8000-00805F9B34FB`
- Telemetry frame: `SNSR <flow> <encoder_position> <pwm>`
- Serial monitor baud rate: `115200`

The GUI and firmware currently disagree on some command formatting and on the meaning of telemetry fields. This must be resolved before claiming end-to-end validation.

## ESP32 bridge candidate

- Service family: Nordic UART Service
- UART baud rate in code: `57600`
- A bridge comment mentions `9600`; the code and comment must be reconciled.

## Compatibility status

The repository also contains GUI and firmware variants using Nordic UART identifiers, different device names, comma-separated telemetry and other baud rates. These variants must remain clearly separated until one protocol is selected.
