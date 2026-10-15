import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum, StrEnum, auto
from types import MappingProxyType
from typing import Any, ClassVar

from aiomqtt import Client as MqttClient
from pymodbus.client import AsyncModbusTcpClient

from modbus2mqtt.device import Device
from modbus2mqtt.exceptions import InvalidConfigurationError
from modbus2mqtt.modbus import RegisterSet


class Phase(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class TopicScope(Enum):
    TOTAL_ONLY = auto()
    TOTAL_AND_PHASE = auto()
    PHASE_ONLY = auto()


class Measurement(Enum):
    """Standard meter measurements, their MQTT suffixes and publication scopes."""

    VOLTAGE = ("voltage", TopicScope.PHASE_ONLY)
    CURRENT = ("current", TopicScope.PHASE_ONLY)
    ACTIVE_POWER = ("power", TopicScope.TOTAL_AND_PHASE)
    REACTIVE_POWER = ("reactivepower", TopicScope.TOTAL_AND_PHASE)
    APPARENT_POWER = ("apparentpower", TopicScope.TOTAL_AND_PHASE)
    POWER_FACTOR = ("powerfactor", TopicScope.TOTAL_AND_PHASE)
    FREQUENCY = ("frequency", TopicScope.TOTAL_ONLY)
    ACTIVE_ENERGY_IMPORT = ("energy/import", TopicScope.TOTAL_AND_PHASE)
    ACTIVE_ENERGY_EXPORT = ("energy/export", TopicScope.TOTAL_AND_PHASE)
    ACTIVE_ENERGY_NET = ("energy/net", TopicScope.TOTAL_AND_PHASE)
    REACTIVE_ENERGY_IMPORT = ("reactiveenergy/import", TopicScope.TOTAL_AND_PHASE)
    REACTIVE_ENERGY_EXPORT = ("reactiveenergy/export", TopicScope.TOTAL_AND_PHASE)
    REACTIVE_ENERGY_NET = ("reactiveenergy/net", TopicScope.TOTAL_AND_PHASE)
    APPARENT_ENERGY_IMPORT = ("apparentenergy/import", TopicScope.TOTAL_AND_PHASE)
    APPARENT_ENERGY_EXPORT = ("apparentenergy/export", TopicScope.TOTAL_AND_PHASE)
    APPARENT_ENERGY_NET = ("apparentenergy/net", TopicScope.TOTAL_AND_PHASE)
    CURRENT_QUADRANT = ("currentquadrant", TopicScope.TOTAL_AND_PHASE)

    def __init__(self, topic: str, scope: TopicScope):
        self.topic = topic
        self.scope = scope


@dataclass(frozen=True)
class MeterTopic:
    """Device-specific register sources for a standard measurement."""

    total: str | None = None
    single_phase: str | None = None
    phases: Mapping[Phase, str] = field(default_factory=dict)


class Meter(Device):
    """Meter whose supported phases determine its phase-specific output."""

    MEASUREMENT_TOPICS: ClassVar[MappingProxyType[Measurement, MeterTopic]] = MappingProxyType({})
    SINGLE_PHASE_REGISTERS: ClassVar[list[RegisterSet] | None] = None

    def __init__(self, client: AsyncModbusTcpClient, unit: int, mqtt_client: MqttClient, mqtt_prefix: str, config: dict):
        super().__init__(client, unit, mqtt_client, mqtt_prefix, config)
        self._configured_phase: Phase | None = None
        if "phase" in config:
            try:
                self._configured_phase = Phase(config["phase"])
            except ValueError, TypeError:
                raise InvalidConfigurationError(f"Invalid phase {config['phase']!r}: expected L1, L2 or L3.") from None

    @property
    def phases(self) -> set[Phase]:
        """Return the phases measured by this meter."""
        raise NotImplementedError

    def _single_phase(self) -> set[Phase]:
        if self._configured_phase is None:
            raise InvalidConfigurationError(f"{self.__class__.__name__} is single-phase and requires a phase setting (L1, L2 or L3).")
        return {self._configured_phase}

    def validate_static_data(self) -> None:
        phases = self.phases
        if len(phases) == 1 and self.SINGLE_PHASE_REGISTERS is not None:
            self.DYNAMIC_REGISTERS = self.SINGLE_PHASE_REGISTERS
        else:
            self.DYNAMIC_REGISTERS = type(self).DYNAMIC_REGISTERS

    def get_topic_values(self) -> Iterator[tuple[str, Any]]:
        phases = self.phases

        def read_value(name: str | None) -> Any:
            if name is not None:
                for container in self.dynamic_registers:
                    value = container.search(rf"^{re.escape(name)}$")
                    if value is not None:
                        return value
            return None

        for measurement, definition in self.MEASUREMENT_TOPICS.items():
            topic = measurement.topic
            scope = measurement.scope
            if scope in (TopicScope.TOTAL_ONLY, TopicScope.TOTAL_AND_PHASE):
                value = read_value(definition.total)
                if value is not None:
                    yield topic, value

            if scope == TopicScope.TOTAL_ONLY:
                continue

            if len(phases) == 1:
                # A single-phase total also represents that phase. Phase-only
                # readings declare their source explicitly in the device class.
                source = definition.single_phase
                if source is None and scope == TopicScope.TOTAL_AND_PHASE:
                    source = definition.total
                value = read_value(source)
                if value is not None:
                    yield f"{topic}/{next(iter(phases))}", value
            else:
                for phase, source in definition.phases.items():
                    if phase in phases:
                        value = read_value(source)
                        if value is not None:
                            yield f"{topic}/{phase}", value
