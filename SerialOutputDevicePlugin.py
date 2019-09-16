# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# SerialConnection is released under the terms of the GPLv3 or higher.

from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin

from UM.Signal import Signal, signalemitter
from UM.Application import Application
from UM.Logger import Logger
from UM.Util import parseBool

from PyQt5.QtCore import QTimer

import time
import json
import re
import base64

from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from cura.PrinterOutput.PrinterOutputModel import PrinterOutputModel

##      This plugin handles the connection detection & creation of output device objects for OctoPrint-connected printers.
#       Zero-Conf is used to detect printers, which are saved in a dict.
#       If we discover an instance that has the same key as the active machine instance a connection is made.
@signalemitter
class SerialOutputDevicePlugin(OutputDevicePlugin):
    def __init__(self) -> None:
        super().__init__()

    ##  Called by OutputDeviceManager to indicate the plugin should start its device detection.
    def start(self):
        pass

    ##  Called by OutputDeviceManager to indicate the plugin should stop its device detection.
    def stop(self):
        pass

    ## Used to check if this adress makes sense to this plugin w.r.t. adding(/removing) a manual device.
    #  /return 'No', 'possible', or 'priority' (in the last case this plugin takes precedence, use with care).
    def canAddManualDevice(self, address: str = "") -> ManualDeviceAdditionAttempt:
        return ManualDeviceAdditionAttempt.POSSIBLE

    ## Add a manual device by the specified address (for example, an IP).
    #  The optional callback is a function with signature func(success: bool, address: str) -> None, where
    #    - success is a bool that indicates if the manual device's information was successfully retrieved.
    #    - address is the address of the manual device.
    def addManualDevice(self, address: str, callback: Optional[Callable[[bool, str], None]] = None) -> None:
        pass

    ## Remove a manual device by either the name and/or the specified address.
    #  Since this may be asynchronous, use the 'removeDeviceSignal' when the machine actually has been added.
    def removeManualDevice(self, key: str, address: Optional[str] = None) -> None:
        pass

    ## Starts to discovery network devices that can be handled by this plugin.
    def startDiscovery(self) -> None:
        pass

    ## Refresh the available/discovered printers for an output device that handles network printers.
    def refreshConnections(self) -> None:
        pass
