# Project catalog

This document is the working inventory for the repository reorganization. The report is kept as a primary reference, but its contents still need manual verification because text extraction is unavailable in the current environment.

## Public project areas

| Area | Current location | Target location | Status |
| --- | --- | --- | --- |
| Project documentation | `README.md`, `report_biomed.pdf`, `Misc/`, `media/` | `README.md`, `docs/`, `mechanical/` | Curate |
| ESP32 main firmware | `firmware/esp32/main/` | `firmware/esp32/main/` | Main candidate |
| ESP32 bridges and sketches | `firmware/esp32/bridges/`, `archive/VibeCoded_AAAh/` | `firmware/esp32/bridges/`, `archive/` | Prototype/history |
| STM32 projects | `STMWorkSpace/` | `firmware/stm32/`, `archive/` | Multiple candidates |
| Python GUI | `GUI/GUIGK2.py` | `software/gui/` | Closest GUI candidate |
| Python tools | `GUI/visualizer.py`, `PythonBLECOMM/` | `software/tools/` | Utilities |
| KiCad boards | `hardware/motherboard-r1/`, `hardware/motherboard-r2/`, `hardware/pogo-adapter/` | `hardware/` | Preserve sources |
| KiCad custom libraries | `hardware/libraries/` | `hardware/libraries/` | Required dependency |
| MATLAB analysis | `Misure/interpolazioni_script/` | `analysis/matlab/` | Analysis source |
| Measurements | `Misure/*.csv` | `data/measurements/selected/` | Select and normalize |
| Datasheets and sensor examples | `docs/references/datasheets/`, `archive/sensor-sdp800/` | `docs/references/`, `archive/` | Review licenses and relevance |

## Verified technical facts

- `ESP32MAIN/Polmone_Firmware/` is the most complete firmware candidate found in the source tree.
- `GUI/GUIGK2.py` is the closest GUI candidate to the ESP32 HM-10 service, but its telemetry interpretation must be corrected or explicitly documented.
- The repository contains both a direct ESP32 architecture and an older STM32 plus ESP32 bridge architecture.
- BLE identifiers, command syntax, telemetry frames and UART baud rates are not uniform across the repository.
- Both `PCB/motherboard/` and `PCB/motherboard_rev2/` contain complete KiCad source sets; physical assembly and test status are not established.
- Measurement CSV files are valuable experimental data, but their headers, units and reported scales are inconsistent.

## Classification rules

- Keep source files, custom KiCad libraries and selected experimental measurements versioned.
- Move useful prototypes and legacy implementations to `archive/` rather than deleting them.
- Ignore caches, editor state, backups, generated manufacturing output, temporary GUI logs and regenerable CAD exports.
- Do not label a firmware/GUI pair as a validated release until the BLE protocol, telemetry semantics and hardware revision are confirmed together.

## Open decisions

- Which motherboard revision was physically assembled and tested?
- Which STM32 project, if any, belongs to the final system?
- Should the public repository include full datasheets and large CAD exports, or link to external sources?
- Which measurement files are representative and safe to publish?
