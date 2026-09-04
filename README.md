# GWM Jolion for Home Assistant

Unofficial Home Assistant integration for **Haval Jolion** using the Russian GWM cloud.

> **0.1.0-alpha.1** — first private test build. Do not treat experimental remote commands as production-ready.

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

## Installation for the first test

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

## Important testing notes

- Start with read-only telemetry.
- Keep the vehicle safely parked in `P`.
- Remote engine/climate tests should be performed outdoors.
- GWM T5 commands are serialized with a cooldown.
- Experimental command buttons are disabled by default in Home Assistant's entity registry.
- Alpha 0.1 supports the first vehicle returned by the GWM account.

## Climate

The alpha exposes:

- `climate.*_klimat`
- `number.*_vremia_raboty_klimata`

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
