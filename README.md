# CH55x_python_flasher
Python based flash/verify tool for the CH55x MCUs

This script is based on work done by:
1. Aaron Christophel: https://github.com/atc1441/chflasher  
2. Guys at mikrokontroller.net forum (reverse engineering the bootloader)  
3. And my own research on flashing procedures used by the original WCH programing software. 

### Script is still in testing phase, please report any issues. More testing and any constructive input will be very welcomed.  
Logging is not implemented for Bootloader v.1.1.  

___
## Requirements:  
1. python3 installed and in PATH
2. pyusb library, install it via:  
   ```python3 -m pip install --user pyusb ```
3. For Windows, use zadig tool (https://zadig.akeo.ie/) to change the driver for the CH55x board to libusb-win32. Linux does not need that step.  

___
## Usage:

```
python3 chflasher.py [-h] [--version] [-f FILE] [-w | -v | -d | -e] [-s]
                    [--log LOG]

optional arguments:
  -h, --help            show this help message and exit
  --version             Show version.
  -f FILE, --file FILE  The target file to be flashed.
  -w, --write           Write file to flash, verify and exit the bootloader
  -v, --verify          Verify flash against the provided file.
  -d, --detect          Detect chip and bootloader version.
  -e, --erase           Erase flash.
  -s, --start_app       Reset and start application.
  --log LOG             Log usb opeations to file.
```
On Linux if you make the script executable:  
```chmod +x chflasher.py```  
you can omit the _python3_ command and run the srcipt directly.  


___
## Examples:

write, verify the blink.bin file and exit the bootloader:  

```python3 chflasher.py -w -f blink.bin```  

write, verify the blink bin file and exit the bootloader, log operations in the write.log file:

```python3 chflasher.py -w -f blink.bin --log write.log```  

verify the flash against the blink.bin file:  

```python3 chflasher.py -v -f blink.bin```   

erase the flash:  

```python3 chflasher.py -e```  

detect chip and bootloader version:  

```python3 chflasher.py -d```  

show help/usage:  

```python3 chflasher.py -h```  

___

Copyright 02.2020 by Piotr Zapart  
www.hexefx.com
