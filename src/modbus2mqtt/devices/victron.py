import asyncio
import logging
import re
from datetime import UTC, datetime
from enum import Enum, auto
from functools import reduce
from operator import iadd
from types import MappingProxyType
from collections import namedtuple


from construct import Adapter, Byte, Int16sb, Int16ub, Int32sb, Int32ub, Int64sb, Int64ub, PaddedString, Padding, Struct

from modbus2mqtt.device import Device
from modbus2mqtt.exceptions import InvalidConfigurationError
from modbus2mqtt.construct_types import Factor
from modbus2mqtt.modbus import RegisterSet

from dataclasses import dataclass, field

@dataclass(frozen=True)
class VariantData:
    static_registers: list[RegisterSet] = field(default_factory=list)
    dynamic_registers: list[RegisterSet] = field(default_factory=list)
    topics: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))


class Variant(Enum):
    SYSTEM = auto()
    BATTERY = auto()
    VEBUS = auto()


class Victron(Device):
    VARIANT_DATA = {
        Variant.SYSTEM: VariantData(
            dynamic_registers=[
                RegisterSet(
                    address=800,
                    format=Struct(
                        "Serial" / PaddedString(12, encoding="ASCII"),
                        # "RelayState1" / Int16ub,
                        # "RelayState2" / Int16ub,
                        Padding((843 - 806) * 2),
                        # "Soc" / Int16ub ,
                    ),
                )
            ],
        ),
        Variant.BATTERY: VariantData(
            dynamic_registers=[
                RegisterSet(
                    address=258,
                    format=Struct(
                        "BatteryPower" / Factor(1, Int16sb),
                        "BatteryVoltage" / Factor(0.01, Int16ub),
                        Padding(2),
                        "BatteryCurrent" / Factor(0.1, Int16sb),
                        "BatteryTemperature" / Factor(0.1, Int16sb),
                        Padding(6),
                        "BatteryStateOfCharge" / Factor(0.1, Int16sb),
                    ),
                ),
                RegisterSet(
                    address=307,
                    format=Struct(
                        "BatteryMaxChargeCurrent" / Factor(0.1, Int16ub),
                        "BatteryMaxDischargeCurrent" / Factor(0.1, Int16ub),
                    ),
                ),
            ],
            topics=MappingProxyType({
                "BatteryPower": "battery/power",
                "BatteryVoltage": "battery/voltage",
                "BatteryCurrent": "battery/current",
                "BatteryTemperature": "battery/temperature",
                "BatteryStateOfCharge": "battery/stateofcharge",
                "BatteryMaxChargeCurrent": "battery/maxchargecurrent",
                "BatteryMaxDischargeCurrent": "battery/maxdischargecurrent",
            }),
        ),
        Variant.VEBUS: VariantData(
            dynamic_registers=[
                RegisterSet(
                    address=33,
                    format=Struct(
                        # "Serial" / PaddedString(12, encoding="ASCII"),
                        # Padding((843-806)*2),
                        "SwitchPosition" / Int16ub,
                        # "RelayState2" / Int16ub,
                        # "Soc" / Int16ub ,
                    ),
                )
            ],
            topics=MappingProxyType({
                "SwitchPosition": "vebus/mode",
            }),
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "variant" not in kwargs["config"]:
            raise InvalidConfigurationError(f"Variant not specified for unit {self.unit}.")

        try:
            self.variant = Variant[kwargs["config"]["variant"].upper()]
            self.STATIC_REGISTERS = self.VARIANT_DATA[self.variant].static_registers
            self.DYNAMIC_REGISTERS = self.VARIANT_DATA[self.variant].dynamic_registers
            self.TOPICS = self.VARIANT_DATA[self.variant].topics

            self.log.info(f"Configured Victron device with variant {self.variant.name} for unit {self.unit}.")
        except KeyError:
            raise InvalidConfigurationError(f"Variant {kwargs['config']['variant']} specified for unit {self.unit} is not supported.")

    @property
    def identifier(self) -> None | str:
        return None

    @property
    def prefix(self) -> str:
        return ""

    # async def get_messages(self):
    #     register_sets = self.VARIANT_DATA[self.variant].register_sets
    #     topics = self.VARIANT_DATA[self.variant].topics

    #     while True:
    #         now = datetime.now(tz=UTC).timestamp()

    #         try:
    #             parsed_data_list = []
    #             for register_set in register_sets:
    #                 data = await self.client.read_holding_registers(
    #                     address=register_set.start_address,
    #                     count=register_set.registers.sizeof() // 2,
    #                     device_id=self.unit,
    #                 )
    #                 parsed_data_list.append(
    #                     register_set.registers.parse(bytes(reduce(iadd, [[v >> 8, v & 0xFF] for v in data.registers], [])))
    #                 )

    #             for name, topic in topics.items():
    #                 for parsed_data in parsed_data_list:
    #                     value = parsed_data.search(rf"^{name}$")
    #                     if value is not None:
    #                         yield {"topic": f"{topic}", "payload": value}

    #         except Exception as e:
    #             logging.error(f"Reading data from Variant {self.variant.name} for unit {self.unit} failed: {e}")

    #         next_wakeup = now + 1
    #         await asyncio.sleep(next_wakeup - datetime.now(tz=UTC).timestamp())

    #     return
