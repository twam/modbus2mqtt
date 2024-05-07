from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from yaml import safe_load
from pathlib import Path
import logging
from pymodbus.client import AsyncModbusTcpClient
import importlib

from .util import to_camel_case
from . import __version__

from aiomqtt import Client as MqttClient, MqttError

import asyncio


class InvalidConfigurationException(Exception):
    pass

def parse_args() -> Namespace:

    parser = ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        add_help=True
        )

    parser.add_argument("-c", "--conf_file",
                        help="Specify config file", metavar="FILE", required = True, type=Path)

    parser.add_argument("-d", "--daemon",
                        help="Run as daemon", action='store_true')

    parser.add_argument("-v", "--verbose",
                        help="Increases log verbosity for each occurence", dest="verbose_count", action="count", default=0)

    parser.add_argument('--version', action='version', version=__version__)

    args = parser.parse_args()

    return args

def parse_config(filename: Path) -> dict:
    try:
        return safe_load(open(filename, "r"))
    except Exception as e:
        logging.error("Can't load yaml file %r (%r)" % (filename, e))
        raise

async def modbus_gateway(name: str, config: dict, mqtt_client: MqttClient, mqtt_prefix: str, classes_config: dict):
    client = AsyncModbusTcpClient(
        host=config['address'],
        port=config['port'],
        # framer=args.framer,
        # timeout=args.timeout,
        # retries=3,
        # reconnect_delay=1,
        # reconnect_delay_max=10,
        )

    await client.connect()

    async with asyncio.TaskGroup() as tg:
        for unit, config in config['devices'].items():
            try:
                module = importlib.import_module(f".devices.{config['class']}", __package__)
            except ModuleNotFoundError:
                raise InvalidConfigurationException(f"Class '{config['class']}' not supported.")

            class_name = to_camel_case(config['class'])

            if not hasattr(module, class_name):
                raise InvalidConfigurationException(f"Class '{config['class']}' not supported.")

            class_ = getattr(module, class_name)

            device_config = classes_config.get(config['class'], {}).copy()
            device_config.update({k: v for k,v in config.items() if k != 'class'})

            device = class_(client=client, unit=unit, mqtt_client=mqtt_client, mqtt_prefix=f"{mqtt_prefix}{config['class']}/", config=device_config)
            tg.create_task(device.task())

    client.close()

async def async_main():
    args = parse_args()

    logging.basicConfig(format="%(asctime)s %(levelname)-6s %(message)s",
                        level=max(3 - args.verbose_count, 0) * 10)

    try:
        config = parse_config(args.conf_file)
    except Exception as e:
        logging.error("Failure while reading configuration file '%s': %r" % (args.conf_file, e))
        return

    while True:
        try:
            async with MqttClient(
                hostname = config['mqtt']['address'],
                port = config['mqtt'].get('port', 1883),
                username = config['mqtt'].get('username', None),
                password = config['mqtt'].get('password', None)
                ) as mqtt_client:
                mqtt_prefix = config['mqtt'].get('prefix', '')

                async with asyncio.TaskGroup() as tg:
                    for name, gateway_config in config['modbus']['gateways'].items():
                        tg.create_task(modbus_gateway(name=name, config=gateway_config, mqtt_client=mqtt_client, mqtt_prefix=mqtt_prefix, classes_config=config['modbus'].get('classes', {})))

        except MqttError as error:
            print(f'Error "{error}". Reconnecting in 1 seconds.')
            await asyncio.sleep(5)


def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

