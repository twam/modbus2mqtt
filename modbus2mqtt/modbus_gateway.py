import asyncio
import importlib
import logging

from aiomqtt import Client as MqttClient
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException

from modbus2mqtt.exceptions import InvalidConfigurationError
from modbus2mqtt.util import to_camel_case


async def modbus_gateway(name: str, config: dict, mqtt_client: MqttClient, mqtt_prefix: str, classes_config: dict):
    while True:
        try:
            try:
                async with AsyncModbusTcpClient(
                    host=config["address"],
                    port=config["port"],
                    # framer=args.framer,
                    # timeout=args.timeout,
                    # retries=3,
                    # reconnect_delay=1,
                    # reconnect_delay_max=10,
                ) as client:
                    # await client.connect()

                    if client.connected:
                        if config.get("devices") is None:
                            logging.info(f"No devices defined for gateway {name}.")
                            return

                        async with asyncio.TaskGroup() as tg:
                            for unit, device_config in config.get("devices").items():
                                try:
                                    module = importlib.import_module(f".devices.{device_config['class']}", __package__)
                                except ModuleNotFoundError:
                                    raise InvalidConfigurationError(f"Class '{device_config['class']}' not supported.")

                                class_name = to_camel_case(device_config["class"])

                                if not hasattr(module, class_name):
                                    raise InvalidConfigurationError(f"Class '{device_config['class']}' not supported.")

                                class_ = getattr(module, class_name)

                                device_config_merged = classes_config.get(device_config["class"], {}).copy()
                                device_config_merged.update({k: v for k, v in device_config.items() if k != "class"})

                                device = class_(
                                    client=client,
                                    unit=unit,
                                    mqtt_client=mqtt_client,
                                    mqtt_prefix=f"{mqtt_prefix}{device_config['class']}/",
                                    config=device_config_merged,
                                )
                                tg.create_task(device.task())

                    else:
                        logging.warning(
                            f"Couldn't connect to gateway {name} at {config['address']}:{config['port']}. Retrying in 1 second.",
                            exc_info=True,
                        )
                        await asyncio.sleep(1)

            except* ConnectionException as e:
                logging.warning(
                    f"Connection to gateway {name} at {config['address']}:{config['port']} failed with {e}. Retrying in 1 second.",
                    exc_info=True,
                )
                await asyncio.sleep(1)

        except ConnectionException as e:
            logging.warning(f"Connection to gateway {name} at {config['address']}:{config['port']} failed with {e}. Retrying in 1 second.")
            await asyncio.sleep(1)

        except asyncio.CancelledError:
            logging.info(f"Task for gateway {name} cancelled.")
            return
