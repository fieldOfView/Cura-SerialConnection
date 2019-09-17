# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# SerialConnection is released under the terms of the GPLv3 or higher.

from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin

from UM.Signal import Signal, signalemitter

import time
import threading
import serial

from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from cura.PrinterOutput.PrinterOutputModel import PrinterOutputModel

##      This plugin handles the connection detection & creation of output device objects for Serial-connected printers.
#       If we see a port that should be connected to the active machine instance a connection is made.
@signalemitter
class SerialOutputDevicePlugin(OutputDevicePlugin):
    def __init__(self, application) -> None:
        if SerialOutputDevicePlugin.__instance is not None:
            raise RuntimeError("Try to create singleton '%s' more than once" % self.__class__.__name__)
        SerialOutputDevicePlugin.__instance = self

        super().__init__()

        self._application = application

        self._update_thread = threading.Thread(target = self._updateThread)
        self._update_thread.setDaemon(True)

        self._check_updates = True

        self._serial_port_list = []

    addSerialPort = Signal()
    removeSerialPort = Signal()

    serialPortsChanged = Signal()

    ##  Called by OutputDeviceManager to indicate the plugin should start its device detection.
    def start(self):
        self._check_updates = True
        self._update_thread.start()

    ##  Called by OutputDeviceManager to indicate the plugin should stop its device detection.
    def stop(self):
        self._check_updates = False

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


    ##  Create a list of serial ports on the system.
    def getSerialPortList(self):
        result = []
        for port in serial.tools.list_ports.comports():
            if not isinstance(port, tuple):
                port = (port.device, port.description, port.hwid)

            result.append(port[0])

        return result


    def _updateThread(self):
        while self._check_updates:
            port_list = self.getSerialPortList()
            self._addRemovePorts(port_list)
            time.sleep(5)

    ##  Helper to identify serial ports (and scan for them)
    def _addRemovePorts(self, serial_ports):
        # First, find and add all new or changed keys
        for serial_port in list(serial_ports):
            if serial_port not in self._serial_port_list:
                self.addSerialPort.emit(serial_port)  # Hack to ensure its created in main thread
        for serial_port in self._serial_port_list:
            if serial_port not in serial_ports:
                self.removeSerialPort.emit(serial_port)  # Hack to ensure its created in main thread

        if list(serial_ports) != self._serial_port_list:
            self._serial_port_list = list(serial_ports)
            self.serialPortsChanged.emit()


    __instance = None # type: SerialOutputDevicePlugin

    @classmethod
    def getInstance(cls, *args, **kwargs) -> "SerialOutputDevicePlugin":
        return cls.__instance