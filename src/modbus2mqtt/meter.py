from collections.abc import Iterator
from enum import StrEnum
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


class Meter(Device):
    """Meter whose supported phases determine its phase-specific output."""

    PHASE_TOPICS: ClassVar[MappingProxyType[str, str]] = MappingProxyType({})
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
        if len(phases) != 1:
            yield from super().get_topic_values()
            return

        phase = next(iter(phases))
        values = dict(super().get_topic_values())
        # Keep aggregate readings, but replace native phase topics with the
        # configured single-phase readings. Never fabricate other phases.
        for topic, value in values.items():
            if topic.rsplit("/", 1)[-1] not in Phase:
                yield topic, value

        for source, topic in self.PHASE_TOPICS.items():
            if source in values:
                yield f"{topic}/{phase}", values[source]
