import asyncio
import logging
import re
from datetime import UTC, datetime
from functools import reduce
from operator import iadd
from types import MappingProxyType

from construct import Float32b, Int32ub, Padding, Struct

from modbus2mqtt.devices import Device


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

    TOPICS = MappingProxyType({
        "ActiveImport": "energy/import",
        "ActiveExport": "energy/export",
        "Voltage": "voltage",
        "Current": "current",
        "ActivePower": "power",
        "Frequency": "frequency",
    })

    @staticmethod
    async def _wait_until(dt: datetime):
        now = datetime.now(tz=UTC)
        await asyncio.sleep((dt - now).total_seconds())

    async def get_messages(self):
        serial_number = await self.client.read_holding_registers(
            address=0xFC00, count=self.SERIAL_NUMBER.sizeof() // 2, slave=self.unit,
        )
        parsed_serial_number = self.SERIAL_NUMBER.parse(
            bytes(reduce(iadd, [[v >> 8, v & 0xFF] for v in serial_number.registers], [])),
        )

        if parsed_serial_number is None:
            logging.error("Could not parse 'serial_number'.")
            return

        serial_number = parsed_serial_number.search("SerialNumber")

        next_send = {}

        while True:
            now = datetime.now(tz=UTC).timestamp()

            measurements = await self.client.read_input_registers(address=0x0000, count=self.MEASUREMENTS.sizeof() // 2, slave=self.unit)
            parsed_measurements = self.MEASUREMENTS.parse(bytes(reduce(iadd, [[v >> 8, v & 0xFF] for v in measurements.registers], [])))

            for name, topic in self.TOPICS.items():
                for parsed_data in [parsed_measurements]:
                    value = parsed_data.search(rf"^{name}$")
                    if value is not None:
                        interval = 5
                        for topic_regex, topic_interval in self.config.get("intervals", {}).items():
                            if re.match(topic_regex, topic):
                                interval = topic_interval
                                break

                        if now > next_send.get(topic, 0):
                            next_send[topic] = (now // interval + 1) * interval
                            yield {'topic': f"{serial_number}/{topic}", 'payload': value}

            next_wakeup = min(next_send.values())

            await asyncio.sleep(next_wakeup - datetime.now(tz=UTC).timestamp())
