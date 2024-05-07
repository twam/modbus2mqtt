from construct import Struct, Int16ub, Int16sb, Int32ub, Int32sb, Int64ub, Int64sb, Seek, Adapter, PaddedString, Padding, Byte
import asyncio
from modbus2mqtt.devices import Device
from datetime import datetime
import re

class Factor(Adapter):
    def __init__(self, factor: float, *args, **kwargs):
        super().__init__(*args, **kwargs)

        match args[0].fmtstr[1]:
            case "b":
                self.maximum_value = 2**7-1

            case "B":
                self.maximum_value = 2**8-1

            case "h":
                self.maximum_value = 2**15-1

            case "H":
                self.maximum_value = 2**16-1

            case "l":
                self.maximum_value = 2**31-1

            case "L":
                self.maximum_value = 2**32-1

            case "q":
                self.maximum_value = 2**63-1

            case "Q":
                self.maximum_value = 2**64-1

            case _:
                raise ValueError(f"Format {args[0].fmtstr[1]} not implemented.")

        self.factor = factor

    def _decode(self, obj, context, path):
        if obj == self.maximum_value:
            return None
        else:
            return obj*self.factor

    def _encode(self, obj, context, path):
        if opb is None:
            return self.maximum_value
        else:
            return obj/self.factor


class AbbMeter(Device):
    PRODUCTDATA_AND_IDENTIFICATION = Struct(
            "SerialNumber" / Int32ub,
            Padding(6*2),
            "MeterFirmwareVersion" / PaddedString(16, encoding="ASCII"),
            "ModbusMappingVersion" / Struct(
                "Major" / Byte,
                "Minor" / Byte,
            ),
            Padding((0x8960-0x8910-1)*2),
            "TypeDesignation" / PaddedString(12, encoding="ASCII")
        )

    ENERGY_TOTAL = Struct(
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
            "ActiveImportCurrency" / Factor(0.001, Int64ub)
        )

    ENERGY_PER_PHASE = Struct(
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

    MEASUREMENTS = Struct(
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
            Padding(3*2),
            "PhaseAngleCurrentL1" / Factor(0.1, Int16sb),
            "PhaseAngleCurrentL2" / Factor(0.1, Int16sb),
            "PhaseAngleCurrentL3" / Factor(0.1, Int16sb),
            "PowerFactorTotal" / Factor(0.001, Int16sb),
            "PowerFactorL1" / Factor(0.001, Int16sb),
            "PowerFactorL2" / Factor(0.001, Int16sb),
            "PowerFactorL3" / Factor(0.001, Int16sb),
            "CurrentQuandrantTotal" / Factor(1, Int16ub),
            "CurrentQuandrantL1" / Factor(1, Int16ub),
            "CurrentQuandrantL2" / Factor(1, Int16ub),
            "CurrentQuandrantL3" / Factor(1, Int16ub),
        )

    TOPICS = {
            "ActiveImport": "energy/import",
            "ActiveExport": "energy/export",
            "ActiveNet": "energy/net",
            "ActiveImportL1": "energy/import/L1",
            "ActiveImportL2": "energy/import/L2",
            "ActiveImportL3": "energy/import/L3",
            "ActiveExportL1": "energy/export/L1",
            "ActiveExportL2": "energy/export/L2",
            "ActiveExportL3": "energy/export/L3",
            "ActiveNetL1": "energy/net/L1",
            "ActiveNetL2": "energy/net/L2",
            "ActiveNetL3": "energy/net/L3",
            "VoltageL1N": "voltage/L1",
            "VoltageL2N": "voltage/L2",
            "VoltageL3N": "voltage/L3",
            "CurrentL1": "current/L1",
            "CurrentL2": "current/L2",
            "CurrentL3": "current/L3",
            "ActivePowerTotal": "power",
            "ActivePowerL1": "power/L1",
            "ActivePowerL2": "power/L2",
            "ActivePowerL3": "power/L3",
            "Frequency": "frequency",
    }

    @staticmethod
    async def _wait_until(dt: datetime):
        now = datetime.now()
        await asyncio.sleep((dt - now).total_seconds())

    async def get_messages(self):
        productdata_and_identification = await self.client.read_holding_registers(address=0x8900, count=self.PRODUCTDATA_AND_IDENTIFICATION.sizeof()//2, slave=self.unit)
        parsed_productdata_and_identification = self.PRODUCTDATA_AND_IDENTIFICATION.parse(bytes(sum([[v >> 8, v&0xFF] for v in productdata_and_identification.registers],[])))

        serial_number = parsed_productdata_and_identification.search('SerialNumber')

        next_send = {}

        while True:
            now = datetime.now().timestamp()

            energy_total = await self.client.read_holding_registers(address=0x5000, count=self.ENERGY_TOTAL.sizeof()//2, slave=self.unit)
            parsed_energy_total = self.ENERGY_TOTAL.parse(bytes(sum([[v >> 8, v&0xFF] for v in energy_total.registers],[])))

            energy_per_phase = await self.client.read_holding_registers(address=0x5460, count=self.ENERGY_PER_PHASE.sizeof()//2, slave=self.unit)
            parsed_energy_per_phase = self.ENERGY_PER_PHASE.parse(bytes(sum([[v >> 8, v&0xFF] for v in energy_per_phase.registers],[])))

            measurements = await self.client.read_holding_registers(address=0x5B00, count=self.MEASUREMENTS.sizeof()//2, slave=self.unit)
            parsed_measurements = self.MEASUREMENTS.parse(bytes(sum([[v >> 8, v&0xFF] for v in measurements.registers],[])))

            for name, topic in self.TOPICS.items():
                for parsed_data in [parsed_energy_total, parsed_energy_per_phase, parsed_measurements]:
                    value = parsed_data.search(rf"^{name}$")
                    if value is not None:
                        interval = 5
                        for topic_regex, topic_interval in self.config.get('intervals', {}).items():
                            if re.match(topic_regex, topic):
                                interval = topic_interval
                                break

                        if now > next_send.get(topic, 0):
                            next_send[topic] = (now//interval + 1) * interval
                            yield f"{serial_number}/{topic}", value


            next_wakeup = min(next_send.values())

            await asyncio.sleep(next_wakeup-datetime.now().timestamp())
