#!/usr/bin/env python3
"""
this tool can flash the CH55x series with bootloader version 1.1 and 2.31
usage:

to check if the chip is detected and see the bootloader version:
python3 chflasher.py -d

to flash an example blink.bin file:
python3 chflasher.py -w -i blink.bin

to erase the flash:
python3 chflasher.py -e

to verify the flash against the blink.bin file
python3 chflasher.py -v -i blink.bin

In addition, a log of usb tx and rx packets can be written for all operations, simply add --log option:
python3 chflasher.py --log=<logfilename> -w -i blink.bin

support for: CH551, CH552, CH554, CH558 and CH559

Copyright by https://ATCnetz.de (Aaron Christophel) you can edit and use this code as you want if you mention me :)

now works with Python 2.7 or Python 3 thanks to adlerweb
you need to install pyusb to use this flasher install it via pip install pyusb
on linux run: sudo apt-get install python-pip and sudo pip install pyusb
on windows you need the zadig tool https://zadig.akeo.ie/ to install the right driver
click on Options and List all devices to show the USB Module, then install the libusb-win32 driver

Rewritten and upgraded by Piotr Zapart / www.hexefx.com on Jan/Feb 2020
things changed / added:
1. Moved all funtcions into a class and restructured the code, fixed pycharm warnings
2. Added __name__ test condition
3. Added help and info options
4. Added options to detect the chip, erase or verify the flash only
5. Optional usb data logging: use the option --log. It will create a
   new log file with all the usb operations logged.
6. Changed the bootkey generator to work as (almost) in the original WCH app
7. Fixed the flash verify issue for larger bin files

07.2021 -- more fixes && updates:
1. Fixed wrong flash erase size for ch559 (thanks toyoshim)
2. Move the flash size configuration for all supported MCUs to a dictionary
3. Added check for supported MCU type
4. Argparse checks if bin file is provided for write or verify
5. Fixed bargraph progress showing >100%
"""

import usb.core
import usb.util
import serial
import sys
import os
import argparse
import traceback
import platform
import random as rnd
from time import localtime, strftime, sleep


class CHflasher:
    chip_v1 = {
        "detect_seq": (
            0xa2, 0x13, 0x55, 0x53, 0x42, 0x20, 0x44, 0x42, 0x47, 0x20, 0x43, 0x48, 0x35, 0x35, 0x39,
            0x20, 0x26, 0x20, 0x49, 0x53, 0x50, 0x00),
        "exit_bootloader": (0xa5, 0x02, 0x01, 0x00),
        "erase_flash": (0xa6, 0x04, 0x00, 0x00, 0x00, 0x00),
        "mode_write": 0xa8,
        "mode_verify": 0xa7
    }
    chip_v2 = {
        "detect_seq": (
            0xa1, 0x12, 0x00, 0x59, 0x11, 0x4d, 0x43, 0x55, 0x20, 0x49, 0x53, 0x50, 0x20, 0x26, 0x20,
            0x57, 0x43, 0x48, 0x2e, 0x43, 0x4e),
        "exit_bootloader": (0xa2, 0x01, 0x00, 0x01),
        "read_config": (0xa7, 0x02, 0x00, 0x1f, 0x00),
        "mode_write": 0xa5,
        "mode_verify": 0xa6,
        "write_cfg": (0xa8, 0x0e, 0x00, 0x07, 0x00, 0xff, 0xff, 0xff, 0xff, 0x03, 0x00, 0x00, 0x00, 0xff,
                      0x4e, 0x00, 0x00)
    }
    # supported chips
    chip_sup = (0x51, 0x52, 0x53, 0x54, 0x58, 0x59)

    chip_defs = {
        "CH551": {   "flash_blocks": 10,
                    "erase_blocks": 10,
                    "boot_addr":    0x3800
        },
        "CH552": {   "flash_blocks": 16,
                    "erase_blocks": 14,
                    "boot_addr":    0x3800
        },
        "CH553": {   "flash_blocks": 10,
                    "erase_blocks": 10,
                    "boot_addr":    0x3800
        },
        "CH554": {   "flash_blocks": 16,
                    "erase_blocks": 14,
                    "boot_addr":    0x3800
        },
        "CH558": {   "flash_blocks": 40,
                    "erase_blocks": 32,
                    "boot_addr":    0xF400
        },
        "CH559": {   "flash_blocks": 64,
                    "erase_blocks": 60,
                    "boot_addr":    0xF400
        }
    }
    txt_sep = '---------------------------------------------------------------------------------'
    version = '2.2'

    device_erase_size = 8
    device_flash_size = 16
    chipid = 0
    chip_symbol = ""
    log_file = None
    bootloader_ver = None
    bootkey = [0] * 8  # bootkey placeholder
    usb_init_done = False
    serial_init_done = False
    upload_port = "usb"
    serial_baud = 57600

    def __init__(self):
        pass

    def __init_usb(self):
        if self.usb_init_done:
            return
        dev = usb.core.find(idVendor=0x4348, idProduct=0x55e0)
        if dev is None:
            print('No CH55x device found, check driver please')
            sys.exit()
        try:
            dev.reset()
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
            dev.set_configuration()
        except usb.core.USBError as ex:
            if str(ex).startswith('[Errno 2]') and platform.system() == 'Darwin':
                # Recent mac fails with the error 'Entity not found'.
                # It just works to continue with set_configuration forcibly.
                dev.set_configuration()
            elif str(ex).startswith('[Errno 13]') and platform.system() == 'Linux':
                print('No access to USB Device, configure udev or execute as root (sudo)')
                print('For udev create /etc/udev/rules.d/99-ch55x.rules')
                print('with one line:')
                print('---')
                print('SUBSYSTEM=="usb", ATTR{idVendor}=="4348", ATTR{idProduct}=="55e0", MODE="666"')
                print('---')
                print('Restart udev: sudo service udev restart')
                print('Reconnect device, should work now!')
                print('Alternativey use the included script:')
                print('sudo ./linux_ch55x_install_udev_rules.sh')
                sys.exit(2)
            else:
                print('Could not access USB Device')
                traceback.print_exc()
                sys.exit(2)
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
        self.epout = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(
            e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        self.epin = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(
            e.bEndpointAddress) == usb.util.ENDPOINT_IN)

        assert self.epout is not None
        assert self.epin is not None
        self.usb_init_done = True

    def __init_serial(self, port):
        if self.serial_init_done:
            return
        self.ser = serial.Serial(timeout=0.15)
        self.ser.port = port
        self.ser.baudrate = self.serial_baud
        self.ser.open()
        if self.ser.is_open:
            self.upload_port = self.ser.name
            print("Port " + self.ser.name + " " + str(self.serial_baud) + " baud open.")
            print("Attempting to start the bootloader via the DTR line...")
            sleep(0.01)
            self.ser.dtr = True
            sleep(0.15)
            self.ser.dtr = False
            sleep(0.1)

            self.ser.dsrdtr = False  # disable
        else:
            self.__errorexit("Serial port not found.")

    def init_port(self, port="usb"):
        if port == "usb":
            self.__init_usb()
        else:  # using serial port
            self.__init_serial(port)
            self.upload_port = port

    def close_port(self):
        if self.upload_port != "usb" and self.ser.is_open:
            self.ser.close()
            print("Closing " + self.ser.name + " port.")

    def set_logger(self, setting, logfile):
        if setting:
            print("Transaction logger ON: " + logfile)
            self.log_file = open(logfile, "w")  # open log file for writing
            print(self.txt_sep, file=self.log_file)
            time = strftime("%a, %d %b %Y %X +0000", localtime())
            print(time, file=self.log_file)
            print(self.txt_sep, file=self.log_file, end="\r\n")

    def close_logger(self):
        if self.log_file is not None:
            self.log_file.close()

    @classmethod
    def show_info(cls):
        print(cls.txt_sep)
        print("CH55x USB bootloader flash tool, version " + cls.version)
        print("Copyright 2021 by Piotr Zapart www.hexefx.com")
        print("Based on work by https://ATCnetz.de (Aaron Christophel)")
        print("Supported chips: CH551, CH552, CH554, CH558 and CH559")
        print(cls.txt_sep)
        exit(0)

    def show_version(self):
        print("version " + self.version)

    example_text = '''--------------------------------------------------------------------------------
    Examples:
    using USB (default):
    python3 chflasher.py -w -f blink.bin 
    \t\twill write, verify the blink bin file and exit the bootloader
    
    python3 chflasher.py -w -f blink.bin --log write.log
    \t\twill do the same as above, but also record all operations in the new write.log file
    
    python3 chflasher.py -v -f blink.bin
    \t\twill verify the flash against the blink.bin file
    
    python3 chflasher.py -e
    \t\twill erase the flash
    
    using UART:
    python3 chflasher.py -p /dev/ttyUSB0 -w -f blink.bin 
    \t\twill write, verify the blink bin file using ttyUSB0 serial port and exit the bootloader
    
    python3 chflasher.py -p COM4 -w -f blink.bin --log write.log
    \t\twill do the same as above using COM4 port, but also record all operations in the new write.log file
        
    '''

    def __print_buffers(self, tx, rx):
        txl = len(tx)
        if type(rx) is not int:
            rxl = len(rx)
        else:
            rxl = 0
        print("add= " + '|'.join('{:02x}'.format(x) for x in range(max(txl, rxl))),
              file=self.log_file)
        if txl:
            print("tx = " + ':'.join('{:02x}'.format(x) for x in tx), file=self.log_file)
        if rxl:
            print("rx = " + ':'.join('{:02x}'.format(x) for x in rx), file=self.log_file)
        else:
            print("rx = " + str(rx), file=self.log_file)

    # better formatting for visual inspection
    def __print_buffer_errors(self, bindata, tx, rx, address):
        if rx[4] != 0x00:
            msg = "ERR"
        elif rx[4] == 0xfe:
            msg = "BUG"
        else:
            msg = "OK "
        print('bin data' + ' ' * 44 + ':'.join('{:02x}'.format(x) for x in bindata), file=self.log_file)
        print('0x{:>04x}'.format(address) + ":" + msg + ':'.join('{:02x}'.format(x) for x in rx), file=self.log_file,
              end=' ')
        if len(rx):
            print(':'.join('{:02x}'.format(x) for x in tx), file=self.log_file)

    @staticmethod
    def __draw_progressbar(percent, bar_len=20):
        print("\r", end="")
        print("[{:<{}}] {:.0f}% ".format("=" * int(bar_len * percent), bar_len, percent * 100), end="")

    def __errorexit(self, errormsg):
        print(self.txt_sep)
        print('Error: ' + errormsg)
        print(self.txt_sep)
        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print(errormsg, file=self.log_file)
            self.log_file.close()
            self.close_port()
        sys.exit()

    def __get_bootkey(self, data_in, sn_sum):
        if data_in[1] < 30:
            return None

        i = int(data_in[1] / 7)
        self.bootkey[0] = data_in[3 + (i * 4)] ^ sn_sum
        self.bootkey[2] = data_in[3 + (i * 1)] ^ sn_sum
        self.bootkey[3] = data_in[3 + (i * 6)] ^ sn_sum
        self.bootkey[4] = data_in[3 + (i * 3)] ^ sn_sum
        self.bootkey[6] = data_in[3 + (i * 5)] ^ sn_sum
        i = int(data_in[1] / 5)
        self.bootkey[1] = data_in[3 + (i * 1)] ^ sn_sum
        self.bootkey[5] = data_in[3 + (i * 3)] ^ sn_sum
        self.bootkey[7] = (self.chipid + self.bootkey[0]) & 0xff
        reply = 0
        for i in range(8):
            reply = (reply + self.bootkey[i]) & 0xff
        return reply

    def __sendcmd(self, cmd, reply_len):
        # default port is USB
        b = []
        cmd = list(cmd)
        if self.upload_port == "usb":
            self.epout.write(cmd)
            if reply_len:
                b = self.epin.read(64)
        else:  # using serial port
            pkt_len = len(cmd) + 3  # 2 bytes preamble + checksum at the end
            chks = 0
            pkt = bytearray(pkt_len)
            pkt[0] = 0x57  # preamble
            pkt[1] = 0xab
            pkt[2:] = cmd.copy()
            for x in pkt[2:]:
                chks = (chks + x) & 0xff
            pkt.append(chks & 0xff)
            self.ser.write(pkt)
            if reply_len:
                b = self.ser.read(reply_len+3)
                if b and b[0] == 0x55 and b[1] == 0xaa:  # we got reply
                    b = b[2:]  # remove preamble
                    chks = 0
                    for x in b[:-1]:
                        chks = (chks + x) & 0xff  # calc checksum
                    if chks != b[-1]:
                        print("UART bootloader reply: checkusm error")
                    else:
                        b = b[:-1]  # remove last checksum
                else:
                    print("MCU UART not responding")
                    print("Try to cycle the power with the PROG button held down.")
                    print("UART Ports:")
                    print("CH554: RXD1 = P1.6, TXD1 = P1.7")
                    print("CH559: RXD  = P0.2, TXD  = P0.3")
                    self.__errorexit("Bootloader not repsonding.")
        return b

    def __detect_bootloader_ver(self):
        if self.bootloader_ver:  # bootloader already detected
            return
        ver = None
        reply = self.__sendcmd(self.chip_v2["detect_seq"], 6)   # get 6 bytes reply
        if self.log_file is not None:
            print("Detecting bootloader version:", file=self.log_file)
            self.__print_buffers(self.chip_v2["detect_seq"], reply)
        if len(reply) == 0:
            self.__errorexit('Bootloader detect: Comm Failed')
        if len(reply) == 2:
            ver = '1.1'
        else:
            ver = '2.3'
        return ver

    def __write_cfg_v2(self):
        reply = self.__sendcmd(self.chip_v2["write_cfg"], 6)    # 6 bytes reply
        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print("Write Config data:", file=self.log_file)
            self.__print_buffers(self.chip_v2["write_cfg"], reply)

    def __erasechipv1(self):
        self.__sendcmd(self.chip_v1["erase_flash"], 6)
        for x in range(self.device_erase_size):
            buffer = self.__sendcmd((0xa9, 0x02, 0x00, x * 4), 6)
            if buffer[0] != 0x00:
                self.__errorexit('Erase Failed')
        print('Flash Erased')

    def __erasechipv2(self):
        tx = (0xa4, 0x01, 0x00, self.device_erase_size)
        reply = self.__sendcmd(tx, 6)
        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print("Erasing flash:", file=self.log_file)
            self.__print_buffers(tx, reply)
        if reply[4] != 0x00:
            self.__errorexit('Erase Failed')
        print('Flash Erased')

    def __exitbootloaderv1(self):
        print("Starting application...")
        self.__sendcmd(self.chip_v1["exit_bootloader"], 0)  # no reply
        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print("Starting application:", file=self.log_file)
            self.__print_buffers(self.chip_v1["exit_bootloader"], "")

    def __exitbootloaderv2(self):
        print("Starting application...")
        # no reply here
        self.__sendcmd(self.chip_v2["exit_bootloader"], 0)  # no reply
        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print("Starting application:", file=self.log_file)
            self.__print_buffers(self.chip_v2["exit_bootloader"], "")

    def __identchipv1(self):
        reply = self.__sendcmd(self.chip_v1["detect_seq"], 2)
        if len(reply) == 2:
            self.chipid = reply[0]
            self.chip_symbol = 'CH5'+ str(self.chipid - 30)
            print('Found ' + self.chip_symbol)
            if self.chipid in self.chip_sup:
                self.device_flash_size = self.chip_defs[self.chip_symbol]["flash_blocks"]
                self.device_erase_size = self.chip_defs[self.chip_symbol]["erase_blocks"]
                print(f'Flash size: {self.device_flash_size} blocks, {self.device_flash_size * 1024} bytes.')
                print(f'Reserved for application: {self.device_erase_size} blocks, {self.device_erase_size * 1024} bytes.')
        else:
            self.__errorexit('Unknown chip')
        cfganswer = self.__sendcmd((0xbb, 0x00), 2)
        if len(cfganswer) == 2:
            print('Bootloader version: ' + str((cfganswer[0] >> 4)) + '.' + str((cfganswer[0] & 0xf)))
        else:
            self.__errorexit('Unknown bootloader')

    def __identchipv2(self):
        reply = self.__sendcmd(self.chip_v2["detect_seq"], 6)
        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print("Chip identification:", file=self.log_file)
            self.__print_buffers(self.chip_v2["detect_seq"], reply)
        if len(reply) == 6:
            self.chipid = reply[4]
            self.chip_symbol = 'CH5' + str(self.chipid - 30)
            print('Found ' + self.chip_symbol)
            if self.chipid in self.chip_sup:
                self.device_flash_size = self.chip_defs[self.chip_symbol]["flash_blocks"]
                self.device_erase_size = self.chip_defs[self.chip_symbol]["erase_blocks"]
                print(f'Flash size: {self.device_flash_size} blocks, {self.device_flash_size * 1024} bytes.')
                print(f'Reserved for application: {self.device_erase_size} blocks, {self.device_erase_size * 1024} bytes.')
            else:
                self.__errorexit('Chip not supported!')
        else:
            self.__errorexit('Unknown chip!')
        read_cfg_reply = self.__sendcmd(self.chip_v2["read_config"], 30)

        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print("Config read:", file=self.log_file)
            self.__print_buffers(self.chip_v2["read_config"], read_cfg_reply)
        if len(read_cfg_reply) == 30:
            print('Bootloader version: ' + str(read_cfg_reply[19]) + '.' + str(read_cfg_reply[20]) +
                  str(read_cfg_reply[21]))
            self.__keyinputv2(read_cfg_reply)
        else:
            self.__errorexit('Unknown bootloader')

        read_cfg_reply = self.__sendcmd(self.chip_v2["read_config"], 30)
        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print("Config read:", file=self.log_file)
            self.__print_buffers(self.chip_v2["read_config"], read_cfg_reply)

    def __keyinputv2(self, cfganswer):
        outbuffer = bytearray()
        outbuffer.append(0xa3)
        outbuffer.append(0x30)
        outbuffer.append(0x00)
        checksum = sum(cfganswer[0x16:0x1a]) & 0xFF  # checksum from the reply of the read_config_data_cmd
        for x in range(0x30):
            outbuffer.append(rnd.randint(0x00, 0xff))  # generate random sequence
        keygen_reply = self.__get_bootkey(outbuffer, checksum)  # calculate the key from the gen. random list
        reply = self.__sendcmd(outbuffer, 6)  # write data
        if reply[4] != keygen_reply:
            print(self.txt_sep)
            print("KEY sum differs!!! calc = " + str(hex(keygen_reply)) + " received = " + str(hex(reply[4])))
            print(self.txt_sep)

        if self.log_file is not None:
            print(self.txt_sep, file=self.log_file)
            print("Key input:", file=self.log_file)
            print("Checksum: " + str(hex(checksum & 0xFF)), file=self.log_file)
            print("ChipID = " + str(hex(self.chipid)), file=self.log_file)
            print("Bootkey = " + ':'.join('{:02x}'.format(x) for x in self.bootkey), file=self.log_file)
            self.__print_buffers(outbuffer, reply)

    def __writefilev1(self, file_name, mode):
        input_file = list(open(file_name, 'rb').read())
        bytes_to_send = len(input_file)
        if mode == self.chip_v1["mode_write"]:
            print('Filesize: ' + str(bytes_to_send) + ' bytes')
        curr_addr = 0
        pkt_length = 0
        while curr_addr < len(input_file):
            outbuffer = bytearray(64)
            if bytes_to_send >= 0x3c:
                pkt_length = 0x3c
            else:
                pkt_length = bytes_to_send
            outbuffer[0] = mode
            outbuffer[1] = pkt_length
            outbuffer[2] = (curr_addr & 0xff)
            outbuffer[3] = ((curr_addr >> 8) & 0xff)
            for x in range(pkt_length):
                outbuffer[x + 4] = input_file[curr_addr + x]
            buffer = self.__sendcmd(outbuffer, 6)
            curr_addr += pkt_length
            bytes_to_send -= pkt_length
            if buffer is not None:
                if buffer[0] != 0x00:
                    if mode == self.chip_v1["mode_write"]:
                        self.__errorexit('Write Failed!!!')
                    elif mode == self.chip_v1["mode_verify"]:
                        self.__errorexit('Verify Failed!!!')
        if mode == self.chip_v1["mode_write"]:
            print('Writing success')
        elif mode == self.chip_v1["mode_verify"]:
            print('Verify success')

    def __writefilev2(self, file_name, mode):
        input_file = list(open(file_name, 'rb').read())
        bytes_to_send = len(input_file)
        if mode == self.chip_v2["mode_write"]:
            print('Filesize: ' + str(bytes_to_send) + ' bytes')
            if self.log_file is not None:
                print(self.txt_sep, file=self.log_file)
                print("Writing " + str(bytes_to_send) + " bytes to Flash.", file=self.log_file)
                print("add=" + ' ' * 24 + '|'.join('{:02x}'.format(x) for x in range(64)),
                      file=self.log_file)
        if mode == self.chip_v2["mode_verify"]:
            if self.log_file is not None:
                print(self.txt_sep, file=self.log_file)
                print("Veryfing " + str(bytes_to_send) + " bytes of Flash.", file=self.log_file)
                print("add=" + ' ' * 24 + '|'.join('{:02x}'.format(x) for x in range(64)),
                      file=self.log_file)
                if bytes_to_send < 32:
                    self.__errorexit('Firmware bin file possibly corrupt.')
        curr_addr = 0
        pkt_length = 0
        # make the file length to be on 8 bytes boundary
        len_bound = len(input_file)
        while len_bound % 8:
            len_bound = len_bound + 1

        while curr_addr < len_bound:
            outbuffer = bytearray(64)
            if bytes_to_send >= 0x38:
                pkt_length = 0x38
            else:
                pkt_length = bytes_to_send

            outbuffer[0] = mode
            outbuffer[1] = (pkt_length + 5)
            outbuffer[2] = 0x00
            outbuffer[3] = (curr_addr & 0xff)
            outbuffer[4] = ((curr_addr >> 8) & 0xff)
            outbuffer[5] = 0x00
            outbuffer[6] = 0x00
            outbuffer[7] = bytes_to_send & 0xff
            # copy the bin data
            for x in range(pkt_length):
                outbuffer[x + 8] = input_file[curr_addr + x]
            # ensure the bin image size is on 8 bytes boundary
            while pkt_length % 8:
                pkt_length = pkt_length + 1
            outbuffer[1] = (pkt_length + 5)  # update the packet length
            # xor the whole 0x38 long area with the bootkey
            for x in range(pkt_length):
                outbuffer[x + 8] = outbuffer[x + 8] ^ self.bootkey[x & 0x07]
            outbuffer = outbuffer[:pkt_length+8]    # trim the last packet

            buffer = self.__sendcmd(outbuffer, 6)

            # --- logger ---
            if self.log_file is not None:
                self.__print_buffer_errors(input_file[curr_addr:curr_addr + pkt_length], outbuffer, buffer, curr_addr)

            curr_addr += pkt_length
            bytes_to_send -= pkt_length

            self.__draw_progressbar(curr_addr / len_bound)

            if buffer is not None:
                if buffer[4] != 0x00 and buffer[4] != 0xfe:
                    if mode == self.chip_v2["mode_write"]:
                        self.__errorexit('Write Failed at address ' + str(curr_addr))
                    elif mode == self.chip_v2["mode_verify"]:
                        # if the logger is ON, do not exit on verify fail, check all the adresses
                        if self.log_file is not None:
                            print("Verify failed at " + '0x{:>04x}'.format(curr_addr))
                        else:
                            self.__errorexit('Verify Failed at address ' + str(curr_addr))
        if mode == self.chip_v2["mode_write"]:
            print('Writing success')
        elif mode == self.chip_v2["mode_verify"]:
            print('Verify success')

    # Write: full service: write the flash, verify and exit the bootloaer
    def write(self, firmware_bin):
        bt_version = self.__detect_bootloader_ver()
        if bt_version == '1.1':
            self.__identchipv1()
            self.__erasechipv1()
            self.__writefilev1(firmware_bin, self.chip_v1["mode_write"])
            self.__writefilev1(firmware_bin, self.chip_v1["mode_verify"])

        if bt_version == '2.3':
            self.__identchipv2()
            self.__erasechipv2()
            self.__writefilev2(firmware_bin, self.chip_v2["mode_write"])
            self.__writefilev2(firmware_bin, self.chip_v2["mode_verify"])


    def verify(self, firmware_bin):
        bt_version = self.__detect_bootloader_ver()
        if bt_version == '1.1':
            self.__identchipv1()
            self.__writefilev1(firmware_bin, self.chip_v1["mode_verify"])

        if bt_version == '2.3':
            self.__identchipv2()
            self.__writefilev2(firmware_bin, self.chip_v2["mode_verify"])


    # erase: stay in bootloader mode?
    def erase(self):
        bt_version = self.__detect_bootloader_ver()
        if bt_version == '1.1':
            self.__identchipv1()
            self.__erasechipv1()
        if bt_version == '2.3':
            self.__identchipv2()
            self.__erasechipv2()

    def detect(self):
        bt_version = self.__detect_bootloader_ver()
        if bt_version == '1.1':
            self.__identchipv1()
        if bt_version == '2.3':
            self.__identchipv2()

    def start_app(self):
        bt_version = self.__detect_bootloader_ver()
        if bt_version == '1.1':
            self.__exitbootloaderv1()
        if bt_version == '2.3':
            self.__exitbootloaderv2()


# ---------------------------------------------------------------------------------


def __main(argv, flash):
    parser = argparse.ArgumentParser(description="CH55x USB bootloader flash tool.",
                                     epilog=flash.example_text,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--version', action='store_true', help="Show version.")
    parser.add_argument('-p', '--port', type=str, default='', help='serial port')
    parser.add_argument('-f', '--file', type=str, default='', help="The target file to be flashed.")

    oper_group = parser.add_mutually_exclusive_group()
    oper_group.add_argument('-w', '--write', action='store_true', default=False, help="Write file to flash, verify and "
                                                                                      "exit the bootloader")
    oper_group.add_argument('-v', '--verify', action='store_true', default=False, help="Verify flash against the"
                                                                                       " provided file.")
    oper_group.add_argument('-d', '--detect', action='store_true', default=False, help="Detect chip and bootloader "
                                                                                       "version.")
    oper_group.add_argument('-e', '--erase', action='store_true', default=False, help="Erase flash.")

    parser.add_argument('-s', '--start_app', action='store_true', default=False, help="Reset and start application.")
    parser.add_argument('--log', type=str, default=None, help="Log usb opeations to file.")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    firmware_bin = None
    upload_port = "usb"

    if args.version:
        flash.show_info()
    if args.port:
        upload_port = args.port
    # choose default usb of serial if provided
    flash.init_port(upload_port)

    if args.log:
        flash.set_logger(True, args.log)
    if args.file:
        if os.path.isfile(args.file):
            firmware_bin = args.file
        else:
            print("File not found")
            sys.exit(2)
    if args.write:
        if firmware_bin:
            flash.write(firmware_bin)
        else:
            print("Please provide the firmware file!!!")
            parser.print_help(sys.stderr)
            sys.exit(1)

    if args.verify:
        if firmware_bin:
            flash.verify(firmware_bin)
        else:
            print("Please provide the firmware file!!!")
            parser.print_help(sys.stderr)
            sys.exit(1)
    if args.detect:
        flash.detect()
    if args.erase:
        flash.erase()
    if args.start_app:
        flash.start_app()

    # close log file if used
    flash.close_logger()
    flash.close_port()


# ---------------------------------------------------------------------------------


if __name__ == "__main__":
    flasher = CHflasher()
    __main(sys.argv[1:], flasher)
