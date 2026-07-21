import logging
import re
from asyncio import sleep
from datetime import UTC, datetime
from functools import reduce
from operator import iadd
from types import MappingProxyType
from typing import ClassVar

from aiomqtt import Client as MqttClient
from construct import Construct, StreamError
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

from modbus2mqtt.logging import PrefixAdapter
from modbus2mqtt.modbus import RegisterSet, RegisterType


class Device:
    STATIC_REGISTERS: ClassVar[list[RegisterSet]] = []
    DYNAMIC_REGISTERS: ClassVar[list[RegisterSet]] = []
    TOPICS: ClassVar[MappingProxyType] = MappingProxyType({})

    def __init__(self, client: AsyncModbusTcpClient, unit: int, mqtt_client: MqttClient, mqtt_prefix: str, config: dict):
        self.client = client
        self.unit = unit
        self.mqtt_client = mqtt_client
        self.mqtt_prefix = mqtt_prefix
        self.config = config

        self.static_registers: list[Construct] = []
        self.dynamic_registers: list[Construct] = []

        # Cache values
        self._identifier = None
        self._prefix = None

        self.log = PrefixAdapter(logging.getLogger(__name__), f"{self.client.ctx.comm_params.host}:{self.client.ctx.comm_params.port}.{self.unit}: ")

    @property
    def identifier(self) -> None | str:
        """
        Returns the identifier (e.g., serial number) of the device, if available.
        """
        if self._identifier is None:
            for container in self.static_registers:
                value = container.search(r"^SerialNumber$")
                if value is not None:
                    self._identifier = str(value)
                    break

        return self._identifier

    @property
    def prefix(self) -> str:
        """
        Returns the MQTT topic prefix for the device.
        """
        if self._prefix is None:
            self._prefix = self.identifier + "/" if self.identifier is not None else f"{self.client.ctx.comm_params.host}:{self.client.ctx.comm_params.port}.{self.unit}/"

        return self._prefix

    async def read_registers(self, address: int, count: int, device_id: int, register_type: RegisterType = RegisterType.HOLDING):
        if register_type == RegisterType.HOLDING:
            read_function = self.client.read_holding_registers
        elif register_type == RegisterType.INPUT:
            read_function = self.client.read_input_registers
        else:
            raise ValueError(f"Unsupported register type '{register_type}'")

        return await read_function(address=address, count=count, device_id=device_id)

    async def read_and_parse(self, address: int, format: Construct, register_type: RegisterType = RegisterType.HOLDING):
        try:
            reply = await self.read_registers(
                address=address,
                count=format.sizeof() // 2,
                device_id=self.unit,
                register_type=register_type,
            )
        except ModbusIOException as e:
            self.log.error(f"Modbus IO exception while reading {format.name} from address 0x{address:04X}: {e.message}")
            return None

        if reply is None:
            self.log.error(f"Couldn't read {format.name} from address 0x{address:04X}")
            return None

        try:
            parsed = format.parse(
                bytes(reduce(iadd, [[v >> 8, v & 0xFF] for v in reply.registers], [])),
            )
        except StreamError as e:
            self.log.error(f"Couldn't parse {format.name}: {e!s}")
            return None

        if parsed is None:
            self.log.error(f"Couldn't parse {format.name}.")
            return None

        return parsed

    async def task(self):
        while True:
            try:
                await self.get_static_data()

                async for kwargs in self.get_messages():
                    await self.publish(**kwargs)

            except ModbusIOException as e:
                self.log.exception(e)
                return

    async def publish(self, topic: str, **kwargs):
        full_topic = self.mqtt_prefix + self.prefix + topic
        await self.mqtt_client.publish(full_topic, **kwargs)

    async def get_static_data(self) -> None:
        self.static_registers = [x for x in [await self.read_and_parse(address=register_set.address, format=register_set.format, register_type=register_set.register_type) for register_set in self.STATIC_REGISTERS] if x is not None]

        if self.identifier is not None:
            self.log.info(f"Found device of type {self.__class__.__name__} with serial number {self.identifier}.")

        for name, topic in self.TOPICS.items():
            for container in self.static_registers:
                value = container.search(rf"^{name}$")
                if value is not None:
                    await self.publish(topic, payload=value, retain=True)

    async def get_messages(self):
        try:
            next_send = {}

            while True:
                now = datetime.now(tz=UTC).timestamp()

                self.dynamic_registers = [x for x in [await self.read_and_parse(address=register_set.address, format=register_set.format, register_type=register_set.register_type) for register_set in self.DYNAMIC_REGISTERS] if x is not None]

                for name, topic in self.TOPICS.items():
                    for container in self.dynamic_registers:
                        value = container.search(rf"^{name}$")
                        if value is not None:
                            interval = 5
                            for topic_regex, topic_interval in self.config.get("intervals", {}).items():
                                if re.match(topic_regex, topic):
                                    interval = topic_interval
                                    break

                            if now > next_send.get(topic, 0):
                                next_send[topic] = (now // interval + 1) * interval
                                yield {"topic": topic, "payload": value}

                next_wakeup = now + 1 if len(next_send) == 0 else min(next_send.values())

                await sleep(next_wakeup - datetime.now(tz=UTC).timestamp())

        except ModbusIOException as e:
            self.log.error(f"unit {self.unit} failed with: {e.message}")

        except ConnectionException:
            self.log.error("Connection failed. Retrying in 5 s.")
            await sleep(5)
