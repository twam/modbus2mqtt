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

Valid values are `L1`, `L2`, and `L3`. Aggregate power and energy topics remain available;
phase-specific topics such as `power/L2`, `voltage/L2`, `current/L2`, and
`energy/import/L2` carry the same single-phase readings. Frequency remains a
meter-wide topic. Voltage and current are published only with a phase suffix
(e.g. `voltage/L2` and `current/L2`), never as bare `voltage` or `current` topics.
No readings are fabricated for the other phases. Phase topics
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

## Meter MQTT layout

All meter classes use the same measurement suffixes beneath their device prefix.
The `Measurement` enum in `modbus2mqtt.meter` is the central catalogue of meter
measurements: each entry defines its MQTT suffix and `TopicScope`. Each device
class maps these enum entries to its register sources using `MeterTopic` in
`MEASUREMENT_TOPICS`, without redefining topic names or scopes. For example:

```python
MEASUREMENT_TOPICS = MappingProxyType({
    Measurement.VOLTAGE: MeterTopic(single_phase="Voltage"),
    Measurement.ACTIVE_POWER: MeterTopic(total="ActivePower"),
    Measurement.FREQUENCY: MeterTopic(total="Frequency"),
})
```

The catalogue covers voltage, current, active/reactive/apparent power, power
factor, frequency, active/reactive/apparent energy (import/export/net), and current
quadrant. A meter publishes only measurements for which it declares sources.

| Scope | Measurements | Published suffixes (example L2) |
| --- | --- | --- |
| Total only | Frequency | `frequency` |
| Total + phase | Active/reactive energy, active/reactive/apparent power, power factor | e.g. `power` and `power/L2` |
| Phase only | Voltage, current | `voltage/L2`, `current/L2` (no bare topics) |

For single-phase meters, a total + phase reading is published as both the total
and the configured phase. For three-phase meters, totals and phase readings come
from their respective registers; totals are never copied to each phase.

SDM120 and ABB both publish `energy/import`, `energy/export`,
`reactiveenergy/import`, `reactiveenergy/export`, `power`, `reactivepower`,
`apparentpower`, `powerfactor`, `frequency`, and phase-qualified voltage/current.
ABB additionally supports `energy/net`, `reactiveenergy/net`, and
`currentquadrant` (total + phase). Missing or unsupported readings are omitted,
not fabricated. Device metadata topics remain separate from this measurement layout.
