import logging

from aiomqtt import Client as MqttClient
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException
from construct import Construct
from functools import reduce
from operator import iadd


class Device:
    def __init__(self, client: AsyncModbusTcpClient, unit: int, mqtt_client: MqttClient, mqtt_prefix: str, config: dict):
        self.client = client
        self.unit = unit
        self.mqtt_client = mqtt_client
        self.mqtt_prefix = mqtt_prefix
        self.config = config

    def format_logstring(self, string: str):
        return f"{self.client.ctx.comm_params.host}:{self.client.ctx.comm_params.port}.{self.unit}: " + string

    async def read_and_parse(self, address: int, format: Construct):
        reply = await self.client.read_holding_registers(
                address=address, count=format.sizeof() // 2, slave=self.unit,
            )

        if reply is None:
            logging.error(self.format_logstring(f"Couldn't read {format.name} from address 0x{address:04X}"))
            return None

        parsed = format.parse(bytes(reduce(iadd, [[v >> 8, v & 0xFF] for v in reply.registers], [])),)

        if parsed is None:
            logging.error(self.format_logstring(f"Couldn't parse {format.name}."))
            return None

        return parsed

    async def task(self):
        while True:
            try:
                async for kwargs in self.get_messages():
                    kwargs['topic'] = self.mqtt_prefix + kwargs['topic']
                    await self.mqtt_client.publish(**kwargs)

            except ModbusIOException as e:
                logging.exception(e)
                return

            # except ConnectionException as e:
            #     logging.error(e, exc_info=True)

    async def get_messages(self):
        return
        yield
