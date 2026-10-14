from types import MappingProxyType
from typing import ClassVar

from aiomqtt import Client as MqttClient
from construct import Float32b, Int32ub, Padding, Struct
from pymodbus.client import AsyncModbusTcpClient

from modbus2mqtt.meter import Meter, Phase
from modbus2mqtt.modbus import RegisterSet, RegisterType


class Sdm120(Meter):
    def __init__(self, client: AsyncModbusTcpClient, unit: int, mqtt_client: MqttClient, mqtt_prefix: str, config: dict):
        super().__init__(client, unit, mqtt_client, mqtt_prefix, config)
        self._single_phase()

    @property
    def phases(self) -> set[Phase]:
        return self._single_phase()

    SERIAL_NUMBER = Struct(
        "SerialNumber" / Int32ub,
    )

    MEASUREMENTS = Struct(
        "Voltage" / Float32b,
        Padding(4 * 2),
        "Current" / Float32b,
        Padding(4 * 2),
        "ActivePower" / Float32b,
        Padding(4 * 2),
        "ApparentPower" / Float32b,
        Padding(4 * 2),
        "ReactivePower" / Float32b,
        Padding(4 * 2),
        "PowerFactor" / Float32b,
        Padding(0x26 * 2),
        "Frequency" / Float32b,
        "ActiveImport" / Float32b,
        "ActiveExport" / Float32b,
        "ReactiveImport" / Float32b,
        "ReactiveExport" / Float32b,
    )

    TOPICS = MappingProxyType(
        {
            "SerialNumber": "serial_number",
            "ActiveImport": "energy/import",
            "ActiveExport": "energy/export",
            "ReactiveImport": "reactiveenergy/import",
            "ReactiveExport": "reactiveenergy/export",
            "Voltage": "voltage",
            "Current": "current",
            "ActivePower": "power",
            "Frequency": "frequency",
        }
    )

    PHASE_TOPICS = MappingProxyType({topic: topic for topic in ("energy/import", "energy/export", "reactiveenergy/import", "reactiveenergy/export", "voltage", "current", "power")})

    STATIC_REGISTERS: ClassVar[list[RegisterSet]] = [
        RegisterSet(address=0xFC00, format=SERIAL_NUMBER),
    ]

    DYNAMIC_REGISTERS: ClassVar[list[RegisterSet]] = [
        RegisterSet(address=0x0000, format=MEASUREMENTS, register_type=RegisterType.INPUT),
    ]
