# Serial Connection

A Cura plugin which enables connecting to serial ports through PrintCore, which is part of PrintRun.

The Serial Connection plugin is an alternative to the USB Printing plugin that is distributed with Cura. It solves three major issues with the USB Printing plugin:
* Cura does not properly (auto-)detect all printers, and a manual port-selection is missing
* Cura tries connecting to all serial ports on startup, resetting all connected printers (and other Arduino-based peripherals)
* A USB connected printer is "seen" by all printer-instances in Cura as "the" USB-connected printer; In case of multiple connected printers, there is no way to see which printer is connected to which serial port

In comparisson to the USB Printing plugin, the Serial Connection plugin differs in approach based on two principles:
* *Automatically discovering printers over USB on each startup and during operation is a bad idea*

	The original plugin tries to connect and communicate with all serial ports to see if it can get a 3d-printer-like response. Connecting to most 3d printers and many other USB-connected devices will reset these devices, potentially leading to interrupted prints or worse. Discovering the same baudrate on each launch, which leads to multiple resets on each serial device, is alse very unnecessary. Instead this plugin uses manual port selection with the option to detect and store the correct baudrate once.
* *Creating a stable print host is hard, even if it is properly maintained*

	Since Ultimaker printers have not supported USB printing since the Ultimaker 2 (september 2013), the USB Printing support has not been maintained other than a couple of patches (each with differing success on different printers). PrintRun, a dedicated printer host application, is better maintained. This plugin reuses the core of PrintRun/Pronterface.

This plugin contains a copy of printcore.py from the PrintRun project here:
https://github.com/kliment/Printrun/blob/master/printrun/printcore.py