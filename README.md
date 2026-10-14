# modbus2mqtt

modbus2mqtt is small Python based script to periodically poll [Modbus](https://de.wikipedia.org/wiki/Modbus) devices
and push the data to a MQTT server.

Currently only Modbus/TCP is supported.

## Single-phase meters

Single-phase meters require a `phase` setting on each device:

```yaml
devices:
  1:
    class: sdm120
    phase: L2
```

Valid values are `L1`, `L2`, and `L3`. Existing aggregate topics remain available;
phase-specific topics such as `power/L2`, `voltage/L2`, `current/L2`, and
`energy/import/L2` carry the same single-phase readings. Frequency remains a
meter-wide topic. No readings are fabricated for the other phases. Phase topics
use the same interval rules as other topics, matched against their full suffix.
Like other device settings, `phase` can also be specified in `modbus.classes` as
a class default. Avoid a class-wide phase default when mixing single-phase and
three-phase ABB meters.

- **SDM120:** always single-phase; omitting `phase` raises a configuration error.
- **ABB B21…:** detected as single-phase from the model number read from the
  meter; `phase` is required. Total energy and power are used for the selected
  phase, and native L1 voltage/current readings are relabeled to that phase. The
  separate per-phase energy register block is not polled.
- **ABB B23…:** detected as three-phase; `phase` must not be configured. Native
  readings for L1, L2, and L3 are published unchanged.
- **Other ABB models**, or a missing model number, raise a configuration error.

Internally, meter classes inherit from `Meter` and expose a `phases: set[Phase]`
property using the `Phase.L1`, `Phase.L2`, and `Phase.L3` enum values. ABB
capabilities and configuration are validated after identification, before
publishing metadata or polling measurements.
