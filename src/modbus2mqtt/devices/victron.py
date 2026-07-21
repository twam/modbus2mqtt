from dataclasses import dataclass, field
from enum import Enum, auto
from types import MappingProxyType
from typing import ClassVar

from construct import Int16sb, Int16ub, PaddedString, Padding, Struct

from modbus2mqtt.construct_types import Factor
from modbus2mqtt.device import Device
from modbus2mqtt.exceptions import InvalidConfigurationError
from modbus2mqtt.modbus import RegisterSet


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
    VARIANT_DATA: ClassVar[dict] = {
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
            topics=MappingProxyType(
                {
                    "BatteryPower": "battery/power",
                    "BatteryVoltage": "battery/voltage",
                    "BatteryCurrent": "battery/current",
                    "BatteryTemperature": "battery/temperature",
                    "BatteryStateOfCharge": "battery/stateofcharge",
                    "BatteryMaxChargeCurrent": "battery/maxchargecurrent",
                    "BatteryMaxDischargeCurrent": "battery/maxdischargecurrent",
                }
            ),
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
            topics=MappingProxyType(
                {
                    "SwitchPosition": "vebus/mode",
                }
            ),
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
