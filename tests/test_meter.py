from types import SimpleNamespace

import pytest
from construct import Container

from modbus2mqtt.devices.abb_meter import AbbMeter
from modbus2mqtt.devices.sdm120 import Sdm120
from modbus2mqtt.exceptions import InvalidConfigurationError
from modbus2mqtt.meter import Meter, Phase


@pytest.fixture
def make_meter(mocker):
    def factory(meter_class, model_number=None, **config):
        client = SimpleNamespace(ctx=SimpleNamespace(comm_params=SimpleNamespace(host="localhost", port=502)))
        meter = meter_class(client=client, unit=1, mqtt_client=mocker.AsyncMock(), mqtt_prefix="modbus/", config=config)
        if model_number is not None:
            meter.static_registers = [Container(TypeDesignation=model_number)]
            meter.validate_static_data()
        return meter

    return factory


@pytest.mark.parametrize("phase", ["L1", "L2", "L3"])
def test_sdm120_phase_aliases(make_meter, phase):
    meter = make_meter(Sdm120, phase=phase)
    assert isinstance(meter, Meter)
    assert meter.phases == {Phase(phase)}
    meter.dynamic_registers = [Container(Voltage=230.0, Current=2.0, ActivePower=460.0, Frequency=50.0, ActiveImport=12.0, ActiveExport=0.0, ReactiveImport=3.0, ReactiveExport=4.0)]

    values = dict(meter.get_topic_values())

    for topic in Sdm120.PHASE_TOPICS:
        assert values[f"{topic}/{phase}"] == values[topic]
    assert values["frequency"] == 50.0
    assert f"frequency/{phase}" not in values
    assert all(topic.rsplit("/", 1)[-1] not in {"L1", "L2", "L3"} - {phase} for topic in values)


def test_sdm120_requires_phase(make_meter):
    with pytest.raises(InvalidConfigurationError, match="requires a phase setting"):
        make_meter(Sdm120)


@pytest.mark.parametrize("phase", ["L1", "L2", "L3"])
def test_abb_single_phase_uses_totals_and_relabels_voltage_current(make_meter, phase):
    meter = make_meter(AbbMeter, model_number="B21 112-100", phase=phase)
    assert meter.phases == {Phase(phase)}
    meter.dynamic_registers = [
        Container(ActiveImport=12.0, ActiveExport=0.0, ActiveNet=12.0, ReactiveImport=3.0, ReactiveExport=1.0, ReactiveNet=2.0),
        Container(VoltageL1N=230.0, VoltageL2N=0.0, VoltageL3N=None, CurrentL1=2.0, CurrentL2=0.0, CurrentL3=None, ActivePowerTotal=460.0, ActivePowerL1=None, ActivePowerL2=0.0, ReactivePowerTotal=10.0, PowerFactorTotal=0.99, CurrentQuadrantTotal=1, Frequency=50.0),
    ]

    values = dict(meter.get_topic_values())

    for topic in ("energy/import", "energy/export", "energy/net", "reactiveenergy/import", "reactiveenergy/export", "reactiveenergy/net", "power", "reactivepower", "powerfactor", "currentquadrant"):
        assert values[f"{topic}/{phase}"] == values[topic]
    assert values[f"voltage/{phase}"] == 230.0
    assert values[f"current/{phase}"] == 2.0
    assert values["frequency"] == 50.0
    assert all(topic.rsplit("/", 1)[-1] not in {"L1", "L2", "L3"} - {phase} for topic in values)
    assert [register.address for register in meter.DYNAMIC_REGISTERS] == [0x5000, 0x5B00]
    assert [register.address for register in AbbMeter.DYNAMIC_REGISTERS] == [0x5000, 0x5460, 0x5B00]


def test_abb_b23_preserves_native_readings(make_meter):
    meter = make_meter(AbbMeter, model_number="B23 112-100")
    assert meter.phases == {Phase.L1, Phase.L2, Phase.L3}
    meter.dynamic_registers = [Container(ActiveImport=12.0, ActiveImportL1=2.0, ActiveImportL2=4.0, ActiveImportL3=6.0, VoltageL1N=230.0, VoltageL2N=231.0, VoltageL3N=232.0)]

    assert dict(meter.get_topic_values()) == {"energy/import": 12.0, "energy/import/L1": 2.0, "energy/import/L2": 4.0, "energy/import/L3": 6.0, "voltage/L1": 230.0, "voltage/L2": 231.0, "voltage/L3": 232.0}
    assert meter.DYNAMIC_REGISTERS is AbbMeter.DYNAMIC_REGISTERS


@pytest.mark.parametrize("meter_class", [Sdm120, AbbMeter])
@pytest.mark.parametrize("phase", [None, 0, 1, 4, True, "l1", "L4", "", [], {}])
def test_invalid_phase_is_rejected(make_meter, meter_class, phase):
    with pytest.raises(InvalidConfigurationError, match="Invalid phase"):
        make_meter(meter_class, phase=phase)


@pytest.mark.parametrize("meter_class", [Sdm120, AbbMeter])
def test_missing_readings_are_not_emulated(make_meter, meter_class):
    meter = make_meter(meter_class, model_number="B21" if meter_class is AbbMeter else None, phase="L2")
    meter.dynamic_registers = [Container(ActiveImport=None, ActivePowerTotal=None, VoltageL1N=None)]

    assert dict(meter.get_topic_values()) == {}


@pytest.mark.asyncio
async def test_phase_topics_have_independent_publish_intervals(make_meter, mocker):
    meter = make_meter(Sdm120, phase="L2", intervals={"^voltage/L2$": 1, "^voltage$": 30})
    mocker.patch.object(meter, "read_and_parse", return_value=Container(Voltage=230.0))
    mocker.patch("modbus2mqtt.device.sleep", new_callable=mocker.AsyncMock)
    clock = mocker.patch("modbus2mqtt.device.datetime")
    clock.now.return_value.timestamp.side_effect = [100, 100, 101.1]

    messages = meter.get_messages()
    try:
        assert await anext(messages) == {"topic": "voltage", "payload": 230.0}
        assert await anext(messages) == {"topic": "voltage/L2", "payload": 230.0}
        assert await anext(messages) == {"topic": "voltage/L2", "payload": 230.0}
    finally:
        await messages.aclose()


@pytest.mark.asyncio
async def test_static_topics_are_not_duplicated(make_meter, mocker):
    meter = make_meter(Sdm120, phase="L2")
    mocker.patch.object(meter, "read_and_parse", return_value=Container(SerialNumber=123))

    await meter.get_static_data()

    meter.mqtt_client.publish.assert_awaited_once_with("modbus/123/serial_number", payload=123, retain=True)


@pytest.mark.parametrize("model", ["B21", "B21 112-100"])
def test_abb_b21_requires_phase(make_meter, model):
    with pytest.raises(InvalidConfigurationError, match="requires a phase setting"):
        make_meter(AbbMeter, model_number=model)


@pytest.mark.parametrize("phase", ["L1", "L2", "L3"])
def test_abb_b23_rejects_phase(make_meter, phase):
    with pytest.raises(InvalidConfigurationError, match="must not have a phase setting"):
        make_meter(AbbMeter, model_number="B23", phase=phase)


@pytest.mark.parametrize("model", [None, "", "B22", "B24", "A41", "b21", "Unknown"])
@pytest.mark.parametrize("config", [{}, {"phase": "L1"}])
def test_unsupported_abb_models_are_rejected(make_meter, model, config):
    meter = make_meter(AbbMeter, **config)
    meter.static_registers = [Container(TypeDesignation=model)]

    with pytest.raises(InvalidConfigurationError, match="Unsupported ABB model"):
        meter.validate_static_data()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "config", "error"),
    [("B21", {}, "requires a phase setting"), ("B23", {"phase": "L2"}, "must not have a phase setting"), ("B24", {}, "Unsupported ABB model"), (None, {}, "Unsupported ABB model")],
)
async def test_abb_validation_precedes_publishing_and_polling(make_meter, mocker, model, config, error):
    meter = make_meter(AbbMeter, **config)
    read = mocker.patch.object(meter, "read_and_parse", return_value=Container(TypeDesignation=model))

    with pytest.raises(InvalidConfigurationError, match=error):
        await meter.task()

    read.assert_awaited_once()
    assert read.call_args.kwargs["address"] == 0x8900
    meter.mqtt_client.publish.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(("model", "config", "addresses"), [("B21", {"phase": "L3"}, [0x5000, 0x5B00]), ("B23", {}, [0x5000, 0x5460, 0x5B00])])
async def test_abb_register_selection_after_identification(make_meter, mocker, model, config, addresses):
    meter = make_meter(AbbMeter, **config)
    mocker.patch.object(meter, "read_and_parse", return_value=Container(TypeDesignation=model))

    await meter.get_static_data()

    assert [register.address for register in meter.DYNAMIC_REGISTERS] == addresses


def test_abb_phase_capabilities_are_not_cached(make_meter):
    meter = make_meter(AbbMeter, model_number="B21", phase="L1")
    assert meter.phases == {Phase.L1}

    meter.static_registers = [Container(TypeDesignation="B23")]
    with pytest.raises(InvalidConfigurationError, match="must not have a phase setting"):
        _ = meter.phases


def test_returned_phase_set_cannot_change_meter_capabilities(make_meter):
    meter = make_meter(Sdm120, phase="L2")
    meter.phases.add(Phase.L3)

    assert meter.phases == {Phase.L2}
