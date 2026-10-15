from types import MappingProxyType
from typing import ClassVar

from construct import Adapter, Byte, Int16sb, Int16ub, Int32sb, Int32ub, Int64sb, Int64ub, PaddedString, Padding, Struct

from modbus2mqtt.exceptions import InvalidConfigurationError
from modbus2mqtt.meter import Measurement, Meter, MeterTopic, Phase
from modbus2mqtt.modbus import RegisterSet


class Factor(Adapter):
    def __init__(self, factor: float, *args, **kwargs):
        super().__init__(*args, **kwargs)

        match args[0].fmtstr[1]:
            case "b":
                self.maximum_value = 2**7 - 1

            case "B":
                self.maximum_value = 2**8 - 1

            case "h":
                self.maximum_value = 2**15 - 1

            case "H":
                self.maximum_value = 2**16 - 1

            case "l":
                self.maximum_value = 2**31 - 1

            case "L":
                self.maximum_value = 2**32 - 1

            case "q":
                self.maximum_value = 2**63 - 1

            case "Q":
                self.maximum_value = 2**64 - 1

            case _:
                raise ValueError(f"Format {args[0].fmtstr[1]} not implemented.")

        self.factor = factor

    def _decode(self, obj, context, path):
        if obj == self.maximum_value:
            return None

        return obj * self.factor

    def _encode(self, obj, context, path):
        if obj is None:
            return self.maximum_value

        return obj / self.factor


class AbbMeter(Meter):
    model_number_key: ClassVar[str] = "TypeDesignation"
    software_version_key: ClassVar[str] = "MeterFirmwareVersion"

    @property
    def phases(self) -> set[Phase]:
        model = self.model_number
        if model is not None and model.startswith("B21"):
            return self._single_phase()
        if model is not None and model.startswith("B23"):
            if "phase" in self.config:
                raise InvalidConfigurationError(f"ABB model {model!r} is three-phase and must not have a phase setting.")
            return set(Phase)
        raise InvalidConfigurationError(f"Unsupported ABB model {model!r}: expected a B21 or B23 model from the identification registers.")

    PRODUCTDATA_AND_IDENTIFICATION = "ProductAndIdentification" / Struct(
        "SerialNumber" / Int32ub,
        Padding(6 * 2),
        "MeterFirmwareVersion" / PaddedString(16, encoding="ASCII"),
        "ModbusMappingVersion"
        / Struct(
            "Major" / Byte,
            "Minor" / Byte,
        ),
        Padding((0x8960 - 0x8910 - 1) * 2),
        "TypeDesignation" / PaddedString(12, encoding="ASCII"),
    )

    PRODUCTDATA_AND_IDENTIFICATION_TOPICS = MappingProxyType(
        {
            "SerialNumber": "serial_number",
            "TypeDesignation": "product_name",
            "MeterFirmwareVersion": "software_version",
        }
    )

    ENERGY_TOTAL = "EnergyTotal" / Struct(
        "ActiveImport" / Factor(0.01, Int64ub),
        "ActiveExport" / Factor(0.01, Int64ub),
        "ActiveNet" / Factor(0.01, Int64sb),
        "ReactiveImport" / Factor(0.01, Int64ub),
        "ReactiveExport" / Factor(0.01, Int64ub),
        "ReactiveNet" / Factor(0.01, Int64sb),
        "ApparentImport" / Factor(0.01, Int64ub),
        "ApparentExport" / Factor(0.01, Int64ub),
        "ApparentNet" / Factor(0.01, Int64sb),
        "ActiveImportCo2" / Factor(0.001, Int64ub),
        "ActiveImportCurrency" / Factor(0.001, Int64ub),
    )

    ENERGY_PER_PHASE = "EnergyPerPhase" / Struct(
        "ActiveImportL1" / Factor(0.01, Int64ub),
        "ActiveImportL2" / Factor(0.01, Int64ub),
        "ActiveImportL3" / Factor(0.01, Int64ub),
        "ActiveExportL1" / Factor(0.01, Int64ub),
        "ActiveExportL2" / Factor(0.01, Int64ub),
        "ActiveExportL3" / Factor(0.01, Int64ub),
        "ActiveNetL1" / Factor(0.01, Int64sb),
        "ActiveNetL2" / Factor(0.01, Int64sb),
        "ActiveNetL3" / Factor(0.01, Int64sb),
        "ReactiveImportL1" / Factor(0.01, Int64ub),
        "ReactiveImportL2" / Factor(0.01, Int64ub),
        "ReactiveImportL3" / Factor(0.01, Int64ub),
        "ReactiveExportL1" / Factor(0.01, Int64ub),
        "ReactiveExportL2" / Factor(0.01, Int64ub),
        "ReactiveExportL3" / Factor(0.01, Int64ub),
        "ReactiveNetL1" / Factor(0.01, Int64sb),
        "ReactiveNetL2" / Factor(0.01, Int64sb),
        "ReactiveNetL3" / Factor(0.01, Int64sb),
        "ApparentImportL1" / Factor(0.01, Int64ub),
        "ApparentImportL2" / Factor(0.01, Int64ub),
        "ApparentImportL3" / Factor(0.01, Int64ub),
        "ApparentExportL1" / Factor(0.01, Int64ub),
        "ApparentExportL2" / Factor(0.01, Int64ub),
        "ApparentExportL3" / Factor(0.01, Int64ub),
        "ApparentNetL1" / Factor(0.01, Int64sb),
        "ApparentNetL2" / Factor(0.01, Int64sb),
        "ApparentNetL3" / Factor(0.01, Int64sb),
    )

    MEASUREMENTS = "Measurements" / Struct(
        "VoltageL1N" / Factor(0.1, Int32ub),
        "VoltageL2N" / Factor(0.1, Int32ub),
        "VoltageL3N" / Factor(0.1, Int32ub),
        "VoltageL1L2" / Factor(0.1, Int32ub),
        "VoltageLL3L2" / Factor(0.1, Int32ub),
        "VoltageL1L3N" / Factor(0.1, Int32ub),
        "CurrentL1" / Factor(0.01, Int32ub),
        "CurrentL2" / Factor(0.01, Int32ub),
        "CurrentL3" / Factor(0.01, Int32ub),
        "CurrentN" / Factor(0.01, Int32ub),
        "ActivePowerTotal" / Factor(0.01, Int32sb),
        "ActivePowerL1" / Factor(0.01, Int32sb),
        "ActivePowerL2" / Factor(0.01, Int32sb),
        "ActivePowerL3" / Factor(0.01, Int32sb),
        "ReactivePowerTotal" / Factor(0.01, Int32sb),
        "ReactivePowerL1" / Factor(0.01, Int32sb),
        "ReactivePowerL2" / Factor(0.01, Int32sb),
        "ReactivePowerL3" / Factor(0.01, Int32sb),
        "ApparentPowerTotal" / Factor(0.01, Int32sb),
        "ApparentPowerL1" / Factor(0.01, Int32sb),
        "ApparentPowerL2" / Factor(0.01, Int32sb),
        "ApparentPowerL3" / Factor(0.01, Int32sb),
        "Frequency" / Factor(0.01, Int16ub),
        "PhaseAnglePowerTotal" / Factor(0.1, Int16sb),
        "PhaseAnglePowerL1" / Factor(0.1, Int16sb),
        "PhaseAnglePowerL2" / Factor(0.1, Int16sb),
        "PhaseAnglePowerL3" / Factor(0.1, Int16sb),
        "PhaseAngleVoltageL1" / Factor(0.1, Int16sb),
        "PhaseAngleVoltageL2" / Factor(0.1, Int16sb),
        "PhaseAngleVoltageL3" / Factor(0.1, Int16sb),
        Padding(3 * 2),
        "PhaseAngleCurrentL1" / Factor(0.1, Int16sb),
        "PhaseAngleCurrentL2" / Factor(0.1, Int16sb),
        "PhaseAngleCurrentL3" / Factor(0.1, Int16sb),
        "PowerFactorTotal" / Factor(0.001, Int16sb),
        "PowerFactorL1" / Factor(0.001, Int16sb),
        "PowerFactorL2" / Factor(0.001, Int16sb),
        "PowerFactorL3" / Factor(0.001, Int16sb),
        "CurrentQuadrantTotal" / Factor(1, Int16ub),
        "CurrentQuadrantL1" / Factor(1, Int16ub),
        "CurrentQuadrantL2" / Factor(1, Int16ub),
        "CurrentQuadrantL3" / Factor(1, Int16ub),
    )

    TOPICS = MappingProxyType(
        {
            "SerialNumber": "serial_number",
            "TypeDesignation": "product_name",
            "MeterFirmwareVersion": "software_version",
        }
    )

    MEASUREMENT_TOPICS = MappingProxyType(
        {
            Measurement.ACTIVE_ENERGY_IMPORT: MeterTopic(total="ActiveImport", phases={phase: f"ActiveImport{phase}" for phase in Phase}),
            Measurement.ACTIVE_ENERGY_EXPORT: MeterTopic(total="ActiveExport", phases={phase: f"ActiveExport{phase}" for phase in Phase}),
            Measurement.ACTIVE_ENERGY_NET: MeterTopic(total="ActiveNet", phases={phase: f"ActiveNet{phase}" for phase in Phase}),
            Measurement.REACTIVE_ENERGY_IMPORT: MeterTopic(total="ReactiveImport", phases={phase: f"ReactiveImport{phase}" for phase in Phase}),
            Measurement.REACTIVE_ENERGY_EXPORT: MeterTopic(total="ReactiveExport", phases={phase: f"ReactiveExport{phase}" for phase in Phase}),
            Measurement.REACTIVE_ENERGY_NET: MeterTopic(total="ReactiveNet", phases={phase: f"ReactiveNet{phase}" for phase in Phase}),
            Measurement.VOLTAGE: MeterTopic(single_phase="VoltageL1N", phases={phase: f"Voltage{phase}N" for phase in Phase}),
            Measurement.CURRENT: MeterTopic(single_phase="CurrentL1", phases={phase: f"Current{phase}" for phase in Phase}),
            Measurement.ACTIVE_POWER: MeterTopic(total="ActivePowerTotal", phases={phase: f"ActivePower{phase}" for phase in Phase}),
            Measurement.REACTIVE_POWER: MeterTopic(total="ReactivePowerTotal", phases={phase: f"ReactivePower{phase}" for phase in Phase}),
            Measurement.APPARENT_POWER: MeterTopic(total="ApparentPowerTotal", phases={phase: f"ApparentPower{phase}" for phase in Phase}),
            Measurement.POWER_FACTOR: MeterTopic(total="PowerFactorTotal", phases={phase: f"PowerFactor{phase}" for phase in Phase}),
            Measurement.FREQUENCY: MeterTopic(total="Frequency"),
            Measurement.CURRENT_QUADRANT: MeterTopic(total="CurrentQuadrantTotal", phases={phase: f"CurrentQuadrant{phase}" for phase in Phase}),
        }
    )

    STATIC_REGISTERS: ClassVar[list[RegisterSet]] = [
        RegisterSet(address=0x8900, format=PRODUCTDATA_AND_IDENTIFICATION),
    ]

    DYNAMIC_REGISTERS: ClassVar[list[RegisterSet]] = [
        RegisterSet(address=0x5000, format=ENERGY_TOTAL),
        RegisterSet(address=0x5460, format=ENERGY_PER_PHASE),
        RegisterSet(address=0x5B00, format=MEASUREMENTS),
    ]

    # Single-phase models do not need the separate per-phase energy block.
    SINGLE_PHASE_REGISTERS: ClassVar[list[RegisterSet]] = [
        RegisterSet(address=0x5000, format=ENERGY_TOTAL),
        RegisterSet(address=0x5B00, format=MEASUREMENTS),
    ]
