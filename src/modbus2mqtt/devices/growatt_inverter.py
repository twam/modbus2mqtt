import asyncio
import logging
from datetime import datetime, UTC
from functools import reduce
from operator import iadd
from types import MappingProxyType

from construct import Adapter, Int16ub, Int32ub, PaddedString, Seek, Struct, Padding

from modbus2mqtt.device import Device
from modbus2mqtt.construct_types import Factor
from modbus2mqtt.modbus import RegisterSet, RegisterType


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
        # Seek(35 * 2),
        Padding(24 * 2),
        "OutputPower" / Factor(0.1, Int32ub),
        "GridFrequency" / Factor(0.01, Int16ub),
        "L1ThreePhaseGridVoltage" / Factor(0.1, Int16ub),
        "L1ThreePhaseGridOutputCurrent" / Factor(0.1, Int16ub),
        "L1ThreePhaseGridOutputPower" / Factor(0.1, Int32ub),
        # Seek(53 * 2),
        Padding(11 * 2),
        "TodayGenerateEnergy" / Factor(100, Int32ub),
        "TotalGenerateEnergy" / Factor(100, Int32ub),
        Padding(2 * 2),
        # Seek(59 * 2),
        "PV1EnergyToday" / Factor(100, Int32ub),
        "PV1EnergyTotal" / Factor(100, Int32ub),
        "PV2EnergyToday" / Factor(100, Int32ub),
        "PV2EnergyTotal" / Factor(100, Int32ub),
        # Seek(93 * 2),
        Padding(26 * 2),
        "InverterTemperature" / Factor(0.1, Int16ub),
        # Seek(105 * 2),
        # "FaultMainCode" / Int16ub,
        # "FaultSubCode" / Int16ub,
    )

    HOLDING_FRAME1 = Struct(Padding(1 * 2), "SerialNumber" / PaddedString(30, encoding="ASCII"))

    TOPICS = MappingProxyType(
        {
            "SerialNumber": "serial_number",
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
            "PV1EnergyToday": "1/yieldday",
            "PV1EnergyTotal": "1/yieldtotal",
            "PV2EnergyToday": "2/yieldday",
            "PV2EnergyTotal": "2/yieldtotal",
            # "FaultMainCode": "",
            # "FaultSubCode": "",
        }
    )

    STATIC_REGISTERS = [
        RegisterSet(address=3000, format=HOLDING_FRAME1),
    ]

    DYNAMIC_REGISTERS = [
        RegisterSet(address=0x0, format=INPUT_FRAME1, register_type=RegisterType.INPUT),
    ]
