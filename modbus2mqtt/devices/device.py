import logging

from aiomqtt import Client as MqttClient
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException


class Device:
    def __init__(self, client: AsyncModbusTcpClient, unit: int, mqtt_client: MqttClient, mqtt_prefix: str, config: dict):
        self.client = client
        self.unit = unit
        self.mqtt_client = mqtt_client
        self.mqtt_prefix = mqtt_prefix
        self.config = config

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
