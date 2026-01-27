import asyncio
import logging
import re
from datetime import UTC, datetime
from functools import reduce
from operator import iadd
from types import MappingProxyType

from construct import Float32b, Int32ub, Padding, Struct

from modbus2mqtt.device import Device
from modbus2mqtt.modbus import RegisterSet


class Sdm120(Device):
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
        "ActiveExpoert" / Float32b,
        "ReactiveImport" / Float32b,
        "ReactiveExpoert" / Float32b,
    )

    TOPICS = MappingProxyType(
        {
            "SerialNumber": "serial_number",
            "ActiveImport": "energy/import",
            "ActiveExport": "energy/export",
            "Voltage": "voltage",
            "Current": "current",
            "ActivePower": "power",
            "Frequency": "frequency",
        }
    )

    STATIC_REGISTERS = [
        RegisterSet(address=0xFC00, format=SERIAL_NUMBER),
    ]

    DYNAMIC_REGISTERS = [
        RegisterSet(address=0x0000, format=MEASUREMENTS),
    ]
