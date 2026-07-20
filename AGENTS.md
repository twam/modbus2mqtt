# Agent Guide for modbus2mqtt

## Project Overview

`modbus2mqtt` is an asyncio-based Python service that polls data from Modbus
TCP devices/gateways and publishes the readings to an MQTT broker. Devices are
defined by YAML configuration and implemented as pluggable Python classes.

> **Current scope:** Only Modbus/TCP is implemented. Serial (RTU) support is not
> present yet, although the project name and README leave room for it.

## Repository Layout

```
.
├── src/modbus2mqtt
│   ├── __init__.py            # Package version from importlib.metadata
│   ├── modbus2mqtt.py         # CLI entry point, MQTT client lifecycle, task orchestration
│   ├── config.py              # YAML configuration loader
│   ├── modbus.py              # `RegisterType` enum and `RegisterSet` dataclass
│   ├── modbus_gateway.py      # Per-gateway task: connects to Modbus TCP and starts device tasks
│   ├── device.py              # Base `Device` class with static/dynamic polling and MQTT publish loop
│   ├── construct_types.py     # Custom `construct` adapters (e.g., `Factor`)
│   ├── exceptions.py          # `InvalidConfigurationError`
│   ├── logging.py             # `PrefixAdapter` for contextual log prefixes
│   ├── util.py                # Utility helpers (e.g., `to_camel_case`)
│   ├── lock.py                # Currently empty placeholder
│   └── devices/               # Device-specific register maps
│       ├── __init__.py
│       ├── abb_meter.py
│       ├── growatt_inverter.py
│       ├── sdm120.py
│       └── victron.py
├── config.yaml.sample         # Example configuration
├── pyproject.toml             # Project metadata, dependencies, Ruff config
└── README.md
```

## Architecture

1. **CLI (`modbus2mqtt.py`)**: parses arguments, loads YAML config, opens an
   `aiomqtt.Client`, and starts one task per Modbus gateway using `asyncio.TaskGroup`.
2. **Gateway (`modbus_gateway.py`)**: creates an `AsyncModbusTcpClient` for each
   configured gateway, dynamically imports each device's module/class, instantiates
   it, and runs its main task.
3. **Device (`device.py`)**: base class that handles:
   - Reading/parsing static registers once (`STATIC_REGISTERS`).
   - Looping over dynamic registers (`DYNAMIC_REGISTERS`) and publishing values.
   - Topic prefixing: `<mqtt.prefix><device_class>/<identifier_or_host:port.unit>/`
   - Interval throttling per topic via regex rules from `classes.<class>.intervals`.
4. **Register maps**: each device defines `construct.Struct` layouts describing
   Modbus register ranges and maps field names to MQTT topics in `TOPICS`.

## Development Workflow

This project uses `uv` for packaging and dependency management.

### Install dependencies

```bash
uv sync
```

### Run the application

```bash
uv run modbus2mqtt -c config.yaml
```

Add `-v` or `-vv` to increase log verbosity.

### Lint and format

```bash
uv run ruff check .
uv run ruff format .
```

Ruff is configured in `pyproject.toml` with a line length of 140 and a very
broad rule selection. Avoid changing `tool.ruff` settings unless the project is
being migrated intentionally.

### Tests

The `dev` dependency group includes `pytest`, `pytest-mock`, and
`pytest-asyncio`, but there are currently no tests in the repository. If you
add tests, place them in a `tests/` directory at the repository root and run:

```bash
uv run pytest
```

## Coding Conventions

- **Python version:** `>=3.12`.
- **Imports:** prefer absolute imports inside the `modbus2mqtt` package (see
  existing device files).
- **Style:** follow Ruff's enabled rules. Run `ruff check` and `ruff format`
  before committing.
- **Logging:** use the standard `logging` module. Device code uses
  `PrefixAdapter` for per-device/gateway prefixes.
- **Async:** all I/O must be async. Modbus and MQTT clients are async; never call
  blocking code directly from an async task.
- **Type hints:** current code is partially typed; prefer adding annotations for
  new public APIs.

## Adding a New Device

1. Create `src/modbus2mqtt/devices/<device_name>.py`.
2. Define a class named `to_camel_case(device_name)` (e.g., `abb_meter.py` →
   `AbbMeter`) that inherits from `Device`.
3. Define the device's register maps:
   - `STATIC_REGISTERS: list[RegisterSet]` for one-time-read data such as serial
     numbers or firmware versions.
   - `DYNAMIC_REGISTERS: list[RegisterSet]` for periodically polled telemetry.
4. Define `TOPICS = MappingProxyType({"FieldName": "mqtt/topic", ...})` to map
   parsed field names to MQTT topic suffixes.
5. Optionally override `identifier`/`prefix` if the device does not expose a
   `SerialNumber` field using that exact key.
6. Reference the device class in `config.yaml` under a gateway's `devices` map.

Example skeleton:

```python
from types import MappingProxyType
from construct import Int16ub, Struct

from modbus2mqtt.device import Device
from modbus2mqtt.modbus import RegisterSet, RegisterType


class MyDevice(Device):
    STATIC_REGISTERS = [
        RegisterSet(
            address=0x0000,
            format="Identification" / Struct(
                "SerialNumber" / Int16ub,
            ),
        ),
    ]

    DYNAMIC_REGISTERS = [
        RegisterSet(
            address=0x1000,
            format="Telemetry" / Struct(
                "Temperature" / Int16ub,
            ),
            register_type=RegisterType.HOLDING,
        ),
    ]

    TOPICS = MappingProxyType({
        "SerialNumber": "serial_number",
        "Temperature": "temperature",
    })
```

## Configuration File

See `config.yaml.sample` for a full example. Key sections:

- `mqtt`: broker `address`, `port`, optional `username`/`password`, and topic
  `prefix`.
- `modbus.classes`: per-device-class defaults, especially `intervals`. Interval
  regex keys are matched against MQTT topic suffixes to throttle publish rates.
- `modbus.gateways`: per-gateway `address`/`port`, plus a `devices` map where the
  key is the Modbus unit ID and the value contains `class:` referring to a file
  in `src/modbus2mqtt/devices/`.

## Dependencies of Note

- `pymodbus>=3.11.0,<3.12` for Modbus/TCP client support.
- `aiomqtt>=2.0.0,<3` for MQTT publishing.
- `paho-mqtt>=1.0,<2` is pinned because `aiomqtt` v2 depends on it.
- `construct>=2.10.70,<3` for declarative binary data parsing.
- `PyYAML>=6.0,<7` for configuration loading.

## Known Quirks and Limitations

- **Only Modbus/TCP is implemented.** `README.md` and the project name imply
  serial may be supported in the future, but there is no RTU/serial code path.
- **`src/modbus2mqtt/lock.py`** is empty. There is no device/gateway-wide
  Modbus-bus locking mechanism currently.
- **Error handling in `modbus_gateway.py`** uses both `except*` and `except` for
  `ConnectionException`; when touching this file be careful not to lose the
  retry-on-reconnect behavior.
- **The error formatter in `config.py`** currently uses an invalid f-string
  conversion (`{e:r}`) and will raise a `ValueError` if the YAML load ever fails.
- **Device discovery is class-driven.** The application does not auto-detect
  device types; every unit must be mapped manually in the configuration.

## Versioning

Version is declared in `pyproject.toml` under `[project]` and surfaced at runtime
via `importlib.metadata.version(__name__)`.
