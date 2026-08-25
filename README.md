# Syringe-Based Breathing Simulator

University biomedical engineering project developed by Gruppo Viola: a motorized syringe generates controlled air flow at its outlet. The system combines a BLDC motor with an ESCON 50/5 drive, encoder feedback, Sensirion pressure or mass-flow sensing, PID control, BLE communication and a desktop monitoring GUI.

This repository presents the final ESP32-based system together with its electronics, control software, measurement data and technical documentation. Earlier firmware, interface and hardware iterations are preserved separately as supporting development history.

## System overview

The final firmware runs on an ESP32 and coordinates:

- flow sensing through SDP810 or SFM3300 devices;
- motor control through the ESCON driver;
- incremental encoder feedback and homing signals;
- PID regulation of the generated flow;
- external SPI EEPROM storage;
- HM-10 compatible BLE telemetry and commands.

The final architecture is supported by a custom control board and a desktop BLE interface. Earlier STM32 and ESP32 bridge implementations are preserved as development iterations.

## Repository map

| Area | Contents |
| --- | --- |
| [docs](docs/) | Report, architecture notes, protocol notes and project catalog |
| [firmware](firmware/) | ESP32 and STM32 firmware area |
| [software/gui](software/gui/) | Main desktop control interface, [main_gui.py](software/gui/main_gui.py) |
| [software/tools](software/tools/) | BLE terminal, CSV visualizer and Python dependency notes |
| [hardware](hardware/) | KiCad boards, custom libraries and board documentation |
| [analysis/matlab](analysis/matlab/) | Measurement interpolation and resistance-analysis scripts |
| [data/measurements/raw](data/measurements/raw/) | Original experimental CSV measurements |
| [mechanical/renders](mechanical/renders/) | Syringe assembly render |
| [archive](archive/) | GUI prototypes and duplicate/legacy experiments |
| [docs/references/datasheets](docs/references/datasheets/) | Component reference documents |
| [archive/sensor-sdp800](archive/sensor-sdp800/) | Sensor sample-code project and documentation |

The detailed working inventory is in [docs/PROJECT_CATALOG.md](docs/PROJECT_CATALOG.md).

## Final system

- **Controller:** [firmware/esp32/main](firmware/esp32/main) coordinates sensing, encoder feedback, motor actuation, PID flow regulation, EEPROM storage and BLE communication.
- **Control interface:** [software/gui/main_gui.py](software/gui/main_gui.py) provides BLE discovery, connection management, real-time flow/position/PWM plots, operating modes, calibration controls, logging and emergency stop.
- **Electronics:** [hardware/motherboard-r2](hardware/motherboard-r2) and [hardware/pogo-adapter](hardware/pogo-adapter) contain the KiCad designs for the control board and sensor adapter. The original motherboard design is preserved as [motherboard-r1](hardware/motherboard-r1).
- **Validation data:** [data/measurements/raw](data/measurements/raw/) contains the experimental acquisitions used during characterization and analysis.

## Communication status

The final ESP32 interface uses an HM-10-compatible BLE service (`FFE0/FFE1`) and telemetry frames in the form `SNSR <flow> <encoder_position> <pwm>`. The communication details are summarized in [docs/protocol.md](docs/protocol.md).

The earlier Nordic UART bridge and STM32 variants remain available in [archive](archive/) as development iterations and are not part of the primary ESP32 control path.

## Running the Python tools

The main GUI requires Python packages including PyQt6, pyqtgraph, bleak and qasync. The BLE terminal declares its dependency in [requirements-ble.txt](software/tools/requirements-ble.txt).

The CSV visualizer is a separate Streamlit utility:

```text
streamlit run software/tools/visualizer.py
```

Its expected columns are `Timestamp_s` and `Pressione_Pa`; the raw measurements commonly use `Time_s` and `Pressure_Pa`, so they are not directly interchangeable yet.

## Firmware and hardware

The Arduino ESP32 sketch is located in [firmware/esp32/main](firmware/esp32/main) and uses the local NimBLE-Arduino library in [firmware/esp32/libraries](firmware/esp32/libraries).

KiCad source files are separated from local state, backups and manufacturing exports. The root [.gitignore](.gitignore) excludes regenerable artifacts while keeping source schematics, PCB files, custom libraries and experimental measurements available for review.

## Project documentation

- [Project catalog](docs/PROJECT_CATALOG.md)
- [Communication protocol notes](docs/protocol.md)
- [Project report](docs/report_biomed.pdf)
- [Code-flow diagram](docs/architecture/code-flow-diagram.drawio)
- [Firmware pseudocode](docs/architecture/codice.pseudo)
- [Assembly render](mechanical/renders/syringe-assembly.jpg)

## Development history

Previous ESP32 sketches, STM32 firmware, BLE bridges and GUI prototypes are preserved in [archive](archive/). They document the iterations that led to the final ESP32 architecture, while the project entrypoints above describe the system delivered by the team.
