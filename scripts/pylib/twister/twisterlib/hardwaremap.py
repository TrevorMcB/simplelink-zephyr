#!/usr/bin/env python3
# vim: set syntax=python ts=4 :
#
# Copyright (c) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from multiprocessing import Lock, Value
import re
import platform
import yaml
import scl
import logging
from pathlib import Path
from natsort import natsorted

from twisterlib.environment import ZEPHYR_BASE

try:
    from yaml import CSafeLoader as SafeLoader
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import SafeLoader, Dumper

try:
    from tabulate import tabulate
except ImportError:
    print("Install tabulate python module with pip to use --device-testing option.")


import json
import importlib.resources as resources

# Loads board_ids from package inside importlib
def load_board_ids():
    
    with resources.files("board_ids").joinpath("board_ids.json").open("r") as f:
        return json.load(f)


# global board ids
BOARD_IDS = load_board_ids()



logger = logging.getLogger('twister')
logger.setLevel(logging.DEBUG)


class DUT(object):
    def __init__(self,
                 id=None,
                 serial=None,
                 serial_baud=None,
                 platform=None,
                 product=None,
                 serial_pty=None,
                 connected=False,
                 runner_params=None,
                 pre_script=None,
                 post_script=None,
                 post_flash_script=None,
                 runner=None,
                 flash_timeout=60,
                 flash_with_test=False,
                 flash_before=False):

        self.serial = serial
        self.baud = serial_baud or 115200
        self.platform = platform
        self.serial_pty = serial_pty
        self._counter = Value("i", 0)
        self._available = Value("i", 1)
        self.connected = connected
        self.pre_script = pre_script
        self.id = id
        self.product = product
        self.runner = runner
        self.runner_params = runner_params
        self.flash_before = flash_before
        self.fixtures = []
        self.post_flash_script = post_flash_script
        self.post_script = post_script
        self.probe_id = None
        self.pre_script = pre_script
        self.lock = Lock()
        self.match = False
        self.flash_timeout = flash_timeout
        self.flash_with_test = flash_with_test

    
    def to_dict(self):

        exclude = {
            '_available',
            '_counter',
            'match',
            'vid',          
            'pid',          
            'manufacturer', 
            'lock',
            'fixtures',
            'probe_id',
            'notes',
        }

        d = {}
        for k, v in vars(self).items():
            if k in exclude:
                continue
            if v is not None:
                d[k] = v

        return d
    

    def __repr__(self):
        return f"<{self.platform} ({self.product}) on {self.serial}>"


class HardwareMap:
    schema_path = os.path.join(
        ZEPHYR_BASE, "scripts", "schemas", "twister", "hwmap-schema.yaml"
    )

    manufacturer = [
        'ARM',
        'SEGGER',
        'MBED',
        'STMicroelectronics',
        'Atmel Corp.',
        'Texas Instruments',
        'Texas Instruments Incorporated',
        'Silicon Labs',
        'NXP',
        'NXP Semiconductors',
        'Microchip Technology Inc.',
        'FTDI',
        'Digilent',
        'Microsoft',
    ]

    runner_mapping = {
        'pyocd': [
            'DAPLink CMSIS-DAP',
            'MBED CMSIS-DAP'
        ],
        'jlink': [
            'J-Link',
            'J-Link OB'
        ],
        'openocd': [
            'STM32 STLink', '^XDS110.*', 'STLINK-V3'
        ],
        'dediprog': [
            'TTL232R-3V3',
            'MCP2200 USB Serial Port Emulator'
        ]
    }

    def __init__(self, env=None):
        self.detected = []
        self.duts = []
        self.options = env.options





    def discover(self):
        if self.options.generate_hardware_map:
            self.scan(persistent=self.options.persistent_hardware_map)
            self.save(self.options.generate_hardware_map)
            return 0

        if not self.options.device_testing and self.options.hardware_map:
            self.load(self.options.hardware_map)
            logger.info("Available devices:")
            self.dump(connected_only=True)
            return 0

        if self.options.device_testing:
            if self.options.hardware_map:
                self.load(self.options.hardware_map)
                if not self.options.platform:
                    self.options.platform = []
                    for d in self.duts:
                        if d.connected and d.platform != 'unknown':
                            self.options.platform.append(d.platform)

            elif self.options.device_serial:
                self.add_device(
                    self.options.device_serial,
                    self.options.platform[0],
                    self.options.pre_script,
                    False,
                    baud=self.options.device_serial_baud,
                    flash_timeout=self.options.device_flash_timeout,
                    flash_with_test=self.options.device_flash_with_test,
                    flash_before=self.options.flash_before,
                )

            elif self.options.device_serial_pty:
                self.add_device(
                    self.options.device_serial_pty,
                    self.options.platform[0],
                    self.options.pre_script,
                    True,
                    flash_timeout=self.options.device_flash_timeout,
                    flash_with_test=self.options.device_flash_with_test,
                    flash_before=False,
                )

            if self.options.fixture:
                for d in self.duts:
                    d.fixtures.extend(self.options.fixture)
        return 1



    def summary(self, selected_platforms):


        print("\nHardware distribution summary:\n")


        table = []


        header = ['Board', 'ID', 'Counter']


        for d in self.duts:


            if d.connected and d.platform in selected_platforms:


                row = [d.platform, d.id, d.counter]


                table.append(row)


        print(tabulate(table, headers=header, tablefmt="github"))
    
    def add_device(self, serial, platform, pre_script, is_pty, baud=None, flash_timeout=60, flash_with_test=False, flash_before=False):


        device = DUT(platform=platform, connected=True, pre_script=pre_script, serial_baud=baud,


                     flash_timeout=flash_timeout, flash_with_test=flash_with_test, flash_before=flash_before


                    )


        if is_pty:


            device.serial_pty = serial


        else:


            device.serial = serial





        self.duts.append(device)
        
    def load(self, map_file):
        hwm_schema = scl.yaml_load(self.schema_path)
        duts = scl.yaml_load_verify(map_file, hwm_schema)

        for dut in duts:
            pre_script = dut.get('pre_script')
            post_script = dut.get('post_script')
            post_flash_script = dut.get('post_flash_script')
            flash_timeout = dut.get('flash_timeout') or self.options.device_flash_timeout
            flash_with_test = dut.get('flash_with_test')
            if flash_with_test is None:
                flash_with_test = self.options.device_flash_with_test

            flash_before = dut.get('flash_before')
            serial_pty = dut.get('serial_pty')
            serial = dut.get('serial')
            baud = dut.get('baud')

            if flash_before is None:
                flash_before = (
                    self.options.flash_before and
                    not (flash_with_test or serial_pty)
                )

            platform_name = dut.get('platform')
            id = dut.get('id')
            runner = dut.get('runner')
            runner_params = dut.get('runner_params')
            product = dut.get('product')
            fixtures = dut.get('fixtures', [])
            connected = dut.get('connected') and ((serial or serial_pty) is not None)

            if not connected:
                continue

            new_dut = DUT(
                platform=platform_name,
                product=product,
                runner=runner,
                runner_params=runner_params,
                id=id,
                serial_pty=serial_pty,
                serial=serial,
                serial_baud=baud,
                connected=connected,
                pre_script=pre_script,
                flash_before=flash_before,
                post_script=post_script,
                post_flash_script=post_flash_script,
                flash_timeout=flash_timeout,
                flash_with_test=flash_with_test,
            )

            new_dut.fixtures = fixtures
            # counter/available are there but not used right now
            self.duts.append(new_dut)



    def scan(self, persistent=False):
        from serial.tools import list_ports

        serial_devices = list_ports.comports()
        logger.info("Scanning connected hardware...")

        for d in serial_devices:

            # Only detect TI boards (optional, remove if unwanted)
            if not d.manufacturer or "Texas Instruments" not in d.manufacturer:
                continue

            # XDS110 exposes multiple COM interfaces; keep interface 0 only
            if d.location and not d.location.endswith("0"):
                continue

            
            s_dev = DUT(
                platform="unknown",        
                id=d.serial_number,        # id
                serial=d.device,           # COM
                product="unknown",        
                runner="openocd",          
                connected=True
            )

            #Assign board information based on boar_ids.json
            board_id = s_dev.id or ""
            for prefix, entry in BOARD_IDS.items():
                if(board_id.startswith(prefix)):

                    #assign platform and name. 
                    # if fail/missing, default to unknown


                    boardplatform = entry.get("id", "unknown").lower()
                    s_dev.platform = boardplatform.replace("-", "_")



                    #s_dev.platform = entry.get("id", "unknown")
                    s_dev.product  = entry.get("name", "unknown")
                    break



            self.detected.append(s_dev)







    def save(self, hwm_file):
        self.detected = natsorted(self.detected, key=lambda x: x.serial or '')
        if os.path.exists(hwm_file):
            with open(hwm_file, 'r') as yaml_file:
                
                
                hwm = yaml.load(yaml_file, Loader=SafeLoader)
                
                if hwm:
                    hwm.sort(key=lambda x: x.get('id', ''))

                    for h in hwm:
                        h['connected'] = False
                        h['serial'] = None

                    for _detected in self.detected:
                        for h in hwm:
                            if (_detected.id == h['id']
                                and _detected.product == h['product']
                                and not _detected.match
                                and not h['connected']):
                                h['connected'] = True
                                h['serial'] = _detected.serial
                                _detected.match = True
                                break

                new_duts = [d.to_dict() for d in self.detected if not d.match]

                if hwm:
                    hwm = hwm + new_duts
                else:
                    hwm = new_duts

            with open(hwm_file, 'w') as yaml_file:

                #clear content of map file before filling so previous boards don't show up
                yaml_file.truncate()
                
                yaml.dump(hwm, yaml_file, Dumper=Dumper, default_flow_style=False)

            self.load(hwm_file)
            logger.info("Registered devices:")
            self.dump()

        else:
            dl = []
            for _connected in self.detected:
                d = {
                    'platform': _connected.platform,
                    'id': _connected.id,
                    'runner': _connected.runner,
                    'serial': _connected.serial,
                    'product': _connected.product,
                    'connected': _connected.connected,
                }
                dl.append(d)
            with open(hwm_file, 'w') as yaml_file:
                 #clear content of map file before filling so previous boards don't show up
                yaml_file.truncate()

                yaml.dump(dl, yaml_file, Dumper=Dumper, default_flow_style=False)
            logger.info("Detected devices:")
            self.dump(detected=True)

    def dump(self, filtered=[], header=[], connected_only=False, detected=False):
        print("")
        table = []
        to_show = self.detected if detected else self.duts

        if not header:
            header = ["Platform", "ID", "Serial device"]
        for p in to_show:
            if filtered and p.platform not in filtered:
                continue
            if not connected_only or p.connected:
                table.append([p.platform, p.id, p.serial])

        print(tabulate(table, headers=header, tablefmt="github"))
