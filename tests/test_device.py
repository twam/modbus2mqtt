from types import SimpleNamespace
from typing import ClassVar

import pytest
from construct import Container

from modbus2mqtt.device import Device
from modbus2mqtt.devices.abb_meter import AbbMeter
from modbus2mqtt.modbus import RegisterSet


@pytest.fixture
def device():
    client = SimpleNamespace(ctx=SimpleNamespace(comm_params=SimpleNamespace(host="localhost", port=502)))
    return Device(client=client, unit=1, mqtt_client=None, mqtt_prefix="", config={})


@pytest.mark.parametrize(
    ("property_name", "key"),
    [("model_number", "ModelNumber"), ("serial_number", "SerialNumber"), ("software_version", "SoftwareVersion")],
)
@pytest.mark.parametrize("value", ["example", 123, 0, ""])
def test_metadata_properties_search_nested_static_registers(device, property_name, key, value):
    device.static_registers = [Container(Unrelated="ignored"), Container(Identification=Container({key: value}))]

    assert getattr(device, property_name) == str(value)


@pytest.mark.parametrize(
    ("property_name", "key"),
    [("model_number", "ModelNumber"), ("serial_number", "SerialNumber"), ("software_version", "SoftwareVersion")],
)
def test_metadata_properties_are_static_only_and_not_cached(device, property_name, key):
    device.dynamic_registers = [Container({key: "dynamic"})]
    assert getattr(device, property_name) is None

    device.static_registers = [Container({key: None}), Container({key: "first"}), Container({key: "second"})]
    assert getattr(device, property_name) == "first"

    device.static_registers = [Container({key: "updated"})]
    assert getattr(device, property_name) == "updated"

    device.static_registers = []
    assert getattr(device, property_name) is None


def test_metadata_keys_can_be_overridden(device):
    class CustomDevice(Device):
        model_number_key: ClassVar[str] = "Model.Code"
        serial_number_key: ClassVar[str] = "Serial"
        software_version_key: ClassVar[str] = "Firmware"

    custom_device = CustomDevice(device.client, 1, None, "", {})
    custom_device.static_registers = [Container({"ModelXCode": "wrong", "Model.Code": "model", "Serial": 42, "Firmware": "1.2"})]

    assert custom_device.model_number == "model"
    assert custom_device.serial_number == "42"
    assert custom_device.software_version == "1.2"
    assert custom_device.identifier == "42"
    assert Device.model_number_key == "ModelNumber"


def test_identifier_returns_serial_number(device):
    assert device.identifier is None

    device.static_registers = [Container(SerialNumber=123)]
    assert device.identifier == device.serial_number == "123"

    device.static_registers = [Container(SerialNumber=456)]
    assert device.identifier == device.serial_number == "456"


def test_abb_metadata_keys(device):
    meter = AbbMeter(device.client, 1, None, "", {})
    meter.static_registers = [Container(SerialNumber=123, TypeDesignation="B23", MeterFirmwareVersion="1.2")]

    assert meter.model_number == "B23"
    assert meter.serial_number == "123"
    assert meter.software_version == "1.2"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metadata", "description"),
    [
        ({"SerialNumber": 123, "ModelNumber": "B23", "SoftwareVersion": "1.2"}, " with serial number 123, model B23, software version 1.2"),
        ({"SerialNumber": 123}, " with serial number 123"),
        ({"ModelNumber": "B23", "SoftwareVersion": "1.2"}, " with model B23, software version 1.2"),
        ({}, ""),
    ],
)
async def test_static_data_logs_available_metadata(device, mocker, caplog, metadata, description):
    device.STATIC_REGISTERS = [RegisterSet(address=0, format=mocker.Mock())]
    mocker.patch.object(device, "read_and_parse", new=mocker.AsyncMock(return_value=Container(metadata)))
    mocker.patch.object(Device, "identifier", new_callable=mocker.PropertyMock, return_value="unrelated identifier")

    with caplog.at_level("INFO"):
        await device.get_static_data()

    assert f"Found device of type Device{description}." in caplog.text
