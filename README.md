# GWM Jolion for Home Assistant

Unofficial Home Assistant integration for **Haval Jolion** using the Russian GWM cloud.

> **0.1.0-alpha.2** — private test build with the first bundled GWM Jolion dashboard card.

## Current alpha features

- Russian GWM account login and signed cloud requests
- Vehicle polling, location and T-Box connectivity
- Odometer, fuel, range, tyre pressure and tyre temperature
- Verified Jolion body/status mapping:
  - engine
  - central lock
  - doors
  - windows summary
  - trunk
- Diagnostic raw entities for TPMS states, seat heating, light codes, window learning, GPS and T-Box signal
- `vehicleBasicsInfo` read attempt (non-fatal when unsupported)
- Remote engine start/stop (`0x03`)
- Lock/unlock, trunk, close windows, horn/lights
- Rear defrost and steering-wheel heat commands inherited from the tested GWM RU protocol
- Home Assistant `lock` entity
- Home Assistant `climate` entity
- Separate **Climate run time** number, 5–30 minutes
- Experimental front defrost (`0x0B`) and 60-second cabin ventilation (`0x11`), disabled by default
- Bundled `custom:gwm-jolion-card` dashboard card, loaded automatically by the integration

## Installation

The repository is currently private. The GitHub account connected to HACS must have access to it.

1. HACS → **Custom repositories**
2. Add this repository as **Integration**
3. Install **GWM Jolion**
4. Restart Home Assistant
5. Settings → Devices & services → Add integration → **GWM Jolion**
6. Enter the phone and password used in the Russian GWM app.
7. For remote commands, enable **Remote controls** and enter the vehicle security PIN.

Manual install is also possible by copying:

```text
custom_components/gwm_jolion
```

to:

```text
/config/custom_components/gwm_jolion
```

and restarting Home Assistant.

## Updating from alpha.1 to alpha.2

Replace the complete folder:

```text
/config/custom_components/gwm_jolion
```

with the current repository version and **restart Home Assistant completely**. The dashboard card JavaScript is bundled inside the integration and is loaded automatically after restart.

A hard browser refresh may be useful after updating (`Ctrl+F5` on desktop).

## GWM Jolion dashboard card

Alpha 2 adds the first native project card:

```yaml
type: custom:gwm-jolion-card
```

For an account with one Jolion, no entity IDs are required. The card discovers the integration entities from Home Assistant's entity and device registries.

If several compatible vehicles/devices are present, bind the card to any entity belonging to the desired vehicle:

```yaml
type: custom:gwm-jolion-card
entity: device_tracker.your_jolion_location
```

The card currently displays:

- T-Box online/offline
- engine and central-lock state
- climate state and target temperature
- climate runtime slider, 5–30 min
- fuel, remaining range and odometer
- doors, windows and trunk state
- pressure and temperature for all four tyres
- T-Box cellular signal and GPS state
- last remote command when available

Controls currently included:

- engine start/stop
- lock/unlock
- climate on/off
- climate temperature ±1 °C
- climate runtime 5–30 min
- trunk open/close
- close all windows when reported open
- force vehicle-data refresh

Remote actions show a confirmation dialog by default. It can be disabled in YAML:

```yaml
type: custom:gwm-jolion-card
confirm_controls: false
```

The card is registered in `window.customCards`, so after restart it should also appear in the Home Assistant **Add card** dialog as **GWM Jolion**.

## Important testing notes

- Start with read-only telemetry.
- Keep the vehicle safely parked in `P`.
- Remote engine/climate tests should be performed outdoors.
- GWM T5 commands are serialized with a cooldown.
- Experimental command buttons are disabled by default in Home Assistant's entity registry.
- Alpha 0.1 currently supports the first vehicle returned by the GWM account.

## Climate

The alpha exposes:

- `climate.*`
- `number.*` for **Время работы климата**

The number entity controls the next climate command runtime from 5 to 30 minutes.

For the Russian cloud this build uses:

```text
0x04 / switchOrder=1 → ON
0x04 / switchOrder=0 → OFF
```

and attempts to persist temperature/runtime through `vehicle/modifyVehicleRemoteCtlInfo` before climate start.

## Diagnostics to send when testing

Enable debug logging temporarily:

```yaml
logger:
  logs:
    custom_components.gwm_jolion: debug
```

After a test session, attach the relevant Home Assistant log and describe exactly which physical function was changed.

## Status

The project is intentionally Jolion-first. Additional GWM/Haval models may be considered after the Jolion protocol is stable.

## Credits

This project builds on protocol research and MIT-licensed work from:

- `roblencheg/HAVAL_H3`
- `moryoav/ha-gwm-ev`

See `THIRD_PARTY_NOTICES.md`.
