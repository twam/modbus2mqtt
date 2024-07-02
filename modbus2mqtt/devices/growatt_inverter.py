import asyncio
import logging
from types import MappingProxyType

from construct import Adapter, Int16ub, Int32ub, PaddedString, Seek, Struct

from modbus2mqtt.devices import Device


class Factor(Adapter):
    def __init__(self, factor: float, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.factor = factor

    def _decode(self, obj, context, path):
        return obj * self.factor

    def _encode(self, obj, context, path):
        return obj / self.factor


class GrowattInverter(Device):
    INPUT_FRAME1 = Struct(
        "InverterStatus" / Int16ub,
        "InputPower" / Factor(0.1, Int32ub),
        "PV1Voltage" / Factor(0.1, Int16ub),
        "PV1InputCurrent" / Factor(0.1, Int16ub),
        "PV1InputPower" / Factor(0.1, Int32ub),
        "PV2Voltage" / Factor(0.1, Int16ub),
        "PV2InputCurrent" / Factor(0.1, Int16ub),
        "PV2InputPower" / Factor(0.1, Int32ub),
        Seek(35 * 2),
        "OutputPower" / Factor(0.1, Int32ub),
        "GridFrequency" / Factor(0.01, Int16ub),
        "L1ThreePhaseGridVoltage" / Factor(0.1, Int16ub),
        "L1ThreePhaseGridOutputCurrent" / Factor(0.1, Int16ub),
        "L1ThreePhaseGridOutputPower" / Factor(0.1, Int32ub),
        Seek(53 * 2),
        "TodayGenerateEnergy" / Factor(100, Int32ub),
        "TotalGenerateEnergy" / Factor(100, Int32ub),
        Seek(93 * 2),
        "InverterTemperature" / Factor(0.1, Int16ub),
        Seek(105 * 2),
        "FaultMainCode" / Int16ub,
        "FaultSubCode" / Int16ub,
    )

    HOLDING_FRAME1 = Struct(Seek(1 * 2), "SerialNumber" / PaddedString(30, encoding="ASCII"))

    DATAPOINTS = MappingProxyType({
        "InputPower": "0/powerdc",
        "PV1Voltage": "1/voltage",
        "PV1InputCurrent": "1/current",
        "PV1InputPower": "1/power",
        "PV2Voltage": "2/voltage",
        "PV2InputCurrent": "2/current",
        "PV2InputPower": "2/power",
        #            "OutputPower": "0/power",
        "GridFrequency": "0/frequency",
        "L1ThreePhaseGridVoltage": "0/voltage",
        "L1ThreePhaseGridOutputCurrent": "0/current",
        "L1ThreePhaseGridOutputPower": "0/power",
        "TodayGenerateEnergy": "0/yieldday",
        "TotalGenerateEnergy": "0/yieldtotal",
        "InverterTemperature": "0/temperature",
        # "FaultMainCode": "",
        # "FaultSubCode": "",
    })

    async def get_messages(self):
        holding_frame1 = await self.client.read_holding_registers(address=3000, count=125, slave=self.unit)
        parsed_holding_frame1 = self.HOLDING_FRAME1.parse(bytes(sum([[v >> 8, v & 0xFF] for v in holding_frame1.registers], [])))

        if parsed_holding_frame1 is None:
            logging.error("Could not parse HOLDING_FRAME1.")
            return

        serial_number = parsed_holding_frame1.search("SerialNumber")

        while True:
            input_frame1 = await self.client.read_input_registers(address=0, count=125, slave=self.unit)
            parsed_input_frame1 = self.INPUT_FRAME1.parse(bytes(sum([[v >> 8, v & 0xFF] for v in input_frame1.registers], [])))

            if parsed_input_frame1 is None:
                logging.error("Could not parse INPUT_FRAME1.")
                continue

            for name, topic in self.DATAPOINTS.items():
                value = parsed_input_frame1.search(rf"^{name}$")
                if value is not None:
                    yield f"{serial_number}/{topic}", value

            await asyncio.sleep(5)
