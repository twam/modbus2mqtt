import asyncio
from aiomqtt import Client as MqttClient

class Device():
    def __init__(self, client, unit: int, mqtt_client: MqttClient, mqtt_prefix: str, config: dict):
        self.client = client
        self.unit = unit
        self.mqtt_client = mqtt_client
        self.mqtt_prefix = mqtt_prefix
        self.config = config

    async def task(self):
        async for topic, value in self.get_messages():
            await self.mqtt_client.publish(self.mqtt_prefix+topic, value)

    async def get_messages(self):
        return
        yield
