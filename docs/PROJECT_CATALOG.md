# Project catalog

This document is the repository inventory for the project presented in the root README.

## Public project areas

| Area | Current location | Target location | Status |
| --- | --- | --- | --- |
| Project documentation | `README.md`, `docs/`, `mechanical/` | `README.md`, `docs/`, `mechanical/` | Organized |
| ESP32 main firmware | `firmware/esp32/main/` | `firmware/esp32/main/` | Final system |
| ESP32 bridges and sketches | `firmware/esp32/bridges/` | `firmware/esp32/bridges/`, `archive/` | Prototype/history |
| STM32 projects | `firmware/stm32/` | `firmware/stm32/`, `archive/` | Historical implementations |
| Python GUI | `software/gui/main_gui.py` | `software/gui/` | Final ESP32 control interface |
| Python tools | `software/tools/` | `software/tools/` | Utilities |
| KiCad boards | `hardware/motherboard-r1/`, `hardware/motherboard-r2/`, `hardware/pogo-adapter/` | `hardware/` | Preserve sources |
| KiCad custom libraries | `hardware/libraries/` | `hardware/libraries/` | Required dependency |
| MATLAB analysis | `analysis/matlab/` | `analysis/matlab/` | Analysis source |
| Measurements | `data/measurements/raw/` | `data/measurements/raw/` | Experimental data |
| Datasheets and sensor examples | `docs/references/datasheets/`, `archive/sensor-sdp800/` | `docs/references/`, `archive/` | Review licenses and relevance |

## Verified technical facts

- `firmware/esp32/main/` is the final ESP32 firmware implementation.
- `software/gui/main_gui.py` is the main desktop interface for the ESP32 HM-10 service and `SNSR` telemetry.
- The repository contains both a direct ESP32 architecture and an older STM32 plus ESP32 bridge architecture.
- BLE identifiers, command syntax, telemetry frames and UART baud rates are not uniform across the repository.
- Both `hardware/motherboard-r1/` and `hardware/motherboard-r2/` contain complete KiCad source sets; `motherboard-r2` is the primary board design.
- Measurement CSV files are valuable experimental data, but their headers, units and reported scales are inconsistent.

## Classification rules

- Keep source files, custom KiCad libraries and selected experimental measurements versioned.
- Move useful prototypes and legacy implementations to `archive/` rather than deleting them.
- Ignore caches, editor state, backups, generated manufacturing output, temporary GUI logs and regenerable CAD exports.
- Present the ESP32 firmware and `main_gui.py` as the primary delivered system; keep older variants clearly separated in `archive/`.

## Notes for publication

- `motherboard-r2` is presented as the primary board design; `motherboard-r1` is retained as an earlier board revision.
- The ESP32 firmware and `main_gui.py` are the primary project entrypoints.
- Full datasheets are retained as project references; generated manufacturing output, caches and backups are ignored.
- Raw measurements are retained with their original schemas and documented as experimental data.
