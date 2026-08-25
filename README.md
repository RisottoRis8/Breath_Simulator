# Syringe-Based Breathing Simulator

University biomedical engineering project: a motorized syringe generates controlled air flow at its outlet. The system combines a BLDC motor with an ESCON 50/5 drive, encoder feedback, Sensirion pressure or mass-flow sensing, PID control, BLE communication and a desktop monitoring GUI.

The repository contains the complete development history: firmware experiments, Python interfaces, KiCad boards, measurement data, MATLAB analysis and project documentation. The final controller and the validated end-to-end communication path are still being consolidated.

## System overview

The main firmware candidate runs on an ESP32 and coordinates:

- flow sensing through SDP810 or SFM3300 devices;
- motor control through the ESCON driver;
- incremental encoder feedback and homing signals;
- PID regulation of the generated flow;
- external SPI EEPROM storage;
- HM-10 compatible BLE telemetry and commands.

An older parallel architecture uses an ESP32 BLE-to-UART bridge and STM32L432 firmware. Both architectures are preserved because the repository does not yet prove which controller and motherboard revision form the final assembled system.

## Repository map

| Area | Contents |
| --- | --- |
| [docs](docs/) | Report, architecture notes, protocol notes and project catalog |
| [firmware](firmware/) | ESP32 and STM32 firmware area |
| [software/gui](software/gui/) | Main Python GUI candidate, [GUIGK2.py](software/gui/GUIGK2.py) |
| [software/tools](software/tools/) | BLE terminal, CSV visualizer and Python dependency notes |
| [hardware](hardware/) | KiCad boards, custom libraries and board documentation |
| [analysis/matlab](analysis/matlab/) | Measurement interpolation and resistance-analysis scripts |
| [data/measurements/raw](data/measurements/raw/) | Original experimental CSV measurements |
| [mechanical/renders](mechanical/renders/) | Syringe assembly render |
| [archive](archive/) | GUI prototypes and duplicate/legacy experiments |
| [docs/references/datasheets](docs/references/datasheets/) | Component reference documents |
| [archive/sensor-sdp800](archive/sensor-sdp800/) | Sensor sample-code project and documentation |

The detailed working inventory is in [docs/PROJECT_CATALOG.md](docs/PROJECT_CATALOG.md).

## Current candidates

- **ESP32 firmware:** [firmware/esp32/main](firmware/esp32/main) is the most complete implementation found in the source tree. Its modules cover BLE, sensors, motor control, EEPROM and configuration.
- **Python GUI:** [GUIGK2.py](software/gui/GUIGK2.py) is the closest interface to the ESP32 HM-10 service and `SNSR` telemetry.
- **Hardware:** [motherboard-r1](hardware/motherboard-r1) and [motherboard-r2](hardware/motherboard-r2) are complete KiCad design variants; the [pogo adapter](hardware/pogo-adapter) is a separate board. Their physical assembly and test status still need confirmation.
- **Measurements:** the CSV files under [data/measurements/raw](data/measurements/raw/) are experimental data and use more than one header/unit convention.

## Communication status

The repository currently contains incompatible protocol variants. The ESP32 candidate uses HM-10 UUIDs `FFE0/FFE1` and sends frames in the form `SNSR <flow> <encoder_position> <pwm>`. Other GUI and bridge variants use Nordic UART UUIDs, different commands or different UART baud rates.

The compatibility details and unresolved points are tracked in [docs/protocol.md](docs/protocol.md). In particular, the telemetry semantics and some command formatting between the candidate firmware and GUI still require validation before this project can be presented as a released end-to-end system.

## Running the Python tools

The main GUI requires Python packages including PyQt6, pyqtgraph, bleak and qasync. The BLE terminal declares its current dependency in [requirements-ble.txt](software/tools/requirements-ble.txt). Hardware access and the correct BLE protocol are required for live operation.

The CSV visualizer is a separate Streamlit utility:

```text
streamlit run software/tools/visualizer.py
```

Its expected columns are `Timestamp_s` and `Pressione_Pa`; the raw measurements commonly use `Time_s` and `Pressure_Pa`, so they are not directly interchangeable yet.

## Firmware and hardware

The Arduino ESP32 sketch can be opened from [firmware/esp32/main](firmware/esp32/main) with the Arduino IDE and the required ESP32 board support. The local NimBLE-Arduino library is retained under [firmware/esp32/libraries](firmware/esp32/libraries) until dependency ownership is finalized.

KiCad source files are being separated from local state, backups and manufacturing exports. The root [.gitignore](.gitignore) excludes those regenerable artifacts while keeping source schematics, PCB files, custom libraries and experimental measurements available for review.

## Project documentation

- [Project catalog](docs/PROJECT_CATALOG.md)
- [Communication protocol notes](docs/protocol.md)
- [Project report](docs/report_biomed.pdf)
- [Code-flow diagram](docs/architecture/code-flow-diagram.drawio)
- [Firmware pseudocode](docs/architecture/codice.pseudo)
- [Assembly render](mechanical/renders/syringe-assembly.jpg)

## Limitations and next steps

The next consolidation steps are to identify the assembled motherboard and STM32 project, select one communication protocol, normalize the measurement schema, finish the hardware migration and then verify the firmware-GUI integration on real hardware. Prototype code remains available in [archive](archive/) rather than being deleted.
