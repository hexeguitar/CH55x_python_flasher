# CH55x_python_flasher
Python based flash/verify tool for the CH55x MCUs

This script is based on work done by:
1. Aaron Christophel: https://github.com/atc1441/chflasher  
2. Guys at mikrokontroller.net forum (reverse engineering the bootloader)  
3. And my own research on flashing procedures used by the original WCH programing software. 

___
### Changelog:
2.2 Fixed flash/erase block ranges, added udev install script.
2.1 Added serial port option for bootloader v.2.31 + hardware reboot into bootloader.  
2.0 Fixed flashing algorithm for bootloader v.2.31  
1.0 Initial version

___
### 10.2020 UPDATE:  
Succesfull tests:
- CH552 using bootloader v. 2.4, USB only

___
### 03.2020 UPDATE:  
Succesfull tests:

- CH559, CH554 using bootloader v. 2.31, both USB and UART
- CH551 using bootloader v. 1.1, USB only

___
### TODO:
1. Implement programming via UART - done for bootloader v. 2.31
2. Test more MCUs.   
3. Test version 1 of the bootloader.  
    
Logging and Serial port option is not implemented for Bootloader v.1.1.  

___
## Requirements:  
1. python3 installed and in PATH
2. **pyusb** and **pyserial** libraries, install it via:  
   ```python3 -m pip install --user pyusb pyserial```
3. For Windows, use zadig tool (https://zadig.akeo.ie/) to change the driver for the CH55x board to libusb-win32. Linux does not need that step.  

___
## Usage:

```
python3 chflasher.py [-h] [--version] [-p PORT] [-f FILE] [-w | -v | -d | -e]
                     [-s] [--log LOG]

optional arguments:
  -h, --help            show this help message and exit
  --version             Show version.
  -p PORT, --port PORT  serial port
  -f FILE, --file FILE  The target file to be flashed.
  -w, --write           Write file to flash, verify and exit the bootloader
  -v, --verify          Verify flash against the provided file.
  -d, --detect          Detect chip and bootloader version.
  -e, --erase           Erase flash.
  -s, --start_app       Reset and start application.
  --log LOG             Log  opeations to file.


```
On Linux if you make the script executable:  
```chmod +x chflasher.py```  
you can omit the _python3_ command and run the srcipt directly.  


___
## Examples:

#### Using USB (default method if port parameter is not provided)

write, verify the blink.bin file and exit the bootloader:  

```python3 chflasher.py -w -f blink.bin -s```  

write, verify the blink bin file and exit the bootloader, log operations in the write.log file:

```python3 chflasher.py -w -f blink.bin -s --log write.log```  

verify the flash against the blink.bin file:  

```python3 chflasher.py -v -f blink.bin```   

erase the flash:  

```python3 chflasher.py -e```  

detect chip and bootloader version:  

```python3 chflasher.py -d```  

show help/usage:  

```python3 chflasher.py -h```  


#### Using serial port
To make use of a serial port instead of USB provide the additional parameter:  

```-p PORT ```  

ie on Linux:

```python3 chflasher.py -p /dev/ttyUSB0 -w -f blink.bin```  

or in Windows:  

```python3 chflasher.py -p COM5 -w -f blink.bin```  

___

Copyright 03.2021 by Piotr Zapart  
www.hexefx.com
