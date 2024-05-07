import asyncio
import logging
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from pathlib import Path

from aiomqtt import Client as MqttClient
from aiomqtt import MqttError

from modbus2mqtt import __version__
from modbus2mqtt.config import parse_config
from modbus2mqtt.modbus_gateway import modbus_gateway


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


async def async_main():
    args = parse_args()

    logging.basicConfig(format="%(asctime)s %(levelname)-7s %(message)s",
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

                return 0

        except MqttError as error:
            logging.error(f'Error "{error}". Reconnecting in 1 seconds.')
            await asyncio.sleep(1)

        except Exception as e:
            logging.error("Exception not handled", exc_info=True)
            return -1


def main():
    return asyncio.run(async_main())

if __name__ == "__main__":
    exit(main())

