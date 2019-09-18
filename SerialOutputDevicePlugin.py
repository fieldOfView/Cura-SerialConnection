# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# SerialConnection is released under the terms of the GPLv3 or higher.

from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin

from UM.Logger import Logger
from UM.Signal import Signal, signalemitter
from UM.PluginRegistry import PluginRegistry
from UM.PluginError import PluginNotFoundError

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

        application.pluginsLoaded.connect(self._onPluginsLoaded)

    def _onPluginsLoaded(self) -> None:
        # sabotage USB Printing plugin
        try:
            usb_printing_plugin = PluginRegistry.getInstance().getPluginObject("USBPrinting")
        except PluginNotFoundError:
            return

        Logger.log("d", "Inhibiting serial port detection by the USB Printing plugin")
        usb_printing_plugin._update_thread = threading.Thread(target = self._nilThread)

    def _nilThread(self) -> None:
        Logger.log("d", "The USB serial port detection would start now, but has been inhibited by the Serial Connection plugin")

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