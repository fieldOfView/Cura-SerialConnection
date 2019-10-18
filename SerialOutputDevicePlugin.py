# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# SerialConnection is released under the terms of the GPLv3 or higher.

from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin

from UM.Logger import Logger
from UM.Signal import Signal, signalemitter
from UM.PluginRegistry import PluginRegistry
from UM.PluginError import PluginNotFoundError

from . import SerialOutputDevice

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
    addInstanceSignal = Signal()
    removeInstanceSignal = Signal()

    serialPortsChanged = Signal()

    def __init__(self, application) -> None:
        if SerialOutputDevicePlugin.__instance is not None:
            raise RuntimeError("Try to create singleton '%s' more than once" % self.__class__.__name__)
        SerialOutputDevicePlugin.__instance = self

        super().__init__()

        self._application = application

        self._instances = {} # type: Dict[str, SerialOutputDevice.SerialOutputDevice]
        self._serial_port_list = [] # type: List[str]

        # Because the model needs to be created in the same thread as the QMLEngine, we use a signal.
        self.addInstanceSignal.connect(self._onAddInstance)
        self.removeInstanceSignal.connect(self._onRemoveInstance)
        self._application.globalContainerStackChanged.connect(self._onGlobalContainerStackChanged)

        self._discovery_thread = threading.Thread(target = self._discoveryThread)
        self._discovery_thread.setDaemon(True)
        self._perform_discovery = True

        application.pluginsLoaded.connect(self._onPluginsLoaded)
        application.applicationShuttingDown.connect(self._onApplicationShuttingDown)

    ##  Called by OutputDeviceManager to indicate the plugin should start its device detection.
    def start(self) -> None:
        self._perform_discovery = True
        self._discovery_thread.start()

    ##  Called by OutputDeviceManager to indicate the plugin should stop its device detection.
    def stop(self) -> None:
        self._perform_discovery = False

    ##  Get the list of serial ports on the system.
    def getSerialPortList(self) -> List[str]:
        result = []
        for port in serial.tools.list_ports.comports():
            if not isinstance(port, tuple):
                port = (port.device, port.description, port.hwid)

            result.append(port[0])

        return result

    def _onApplicationShuttingDown(self) -> None:
        ## TODO: investigate why this is necessary
        for key in self._instances:
            if self._instances[key].isConnected():
                self._instances[key].close()
        self._instances = {} # type: Dict[str, SerialOutputDevice.SerialOutputDevice]

    ## Sabotage USBPrinting plugin by replacing its port detection thread before it gets started
    def _onPluginsLoaded(self) -> None:
        try:
            usb_printing_plugin = PluginRegistry.getInstance().getPluginObject("USBPrinting")
        except PluginNotFoundError:
            return

        Logger.log("d", "Inhibiting serial port detection by the USB Printing plugin")
        usb_printing_plugin._update_thread = threading.Thread(target = self._nilThread)

    ## Thread-function that replaces the port detection thread in the USBPrinting plugin
    def _nilThread(self) -> None:
        Logger.log("d", "The USB serial port detection would start now, but has been inhibited by the Serial Connection plugin")
        # This thread exits immediately because we don't want the USBPrinting plugin to find any ports

    ## Thread-function to detect serial ports
    def _discoveryThread(self) -> None:
        while self._perform_discovery:
            port_list = self.getSerialPortList()

            # First, find and add all new or changed keys
            for serial_port in port_list:
                if serial_port not in self._serial_port_list:
                    self.addInstanceSignal.emit(serial_port)  # Hack to ensure its created in main thread
            for serial_port in self._serial_port_list:
                if serial_port not in port_list:
                    self.removeInstanceSignal.emit(serial_port)  # Hack to ensure its created in main thread

            if port_list != self._serial_port_list:
                self._serial_port_list = port_list
                self.serialPortsChanged.emit()

            time.sleep(5)

    ## See if there's an instance that should be connected to the new global stack
    def _onGlobalContainerStackChanged(self) -> None:
        global_container_stack = self._application.getGlobalContainerStack()
        if not global_container_stack:
            return

        for key in self._instances:
            if key == global_container_stack.getMetaDataEntry("serial_port"):
                self._instances[key].connectionStateChanged.connect(self._onInstanceConnectionStateChanged)
                if not self._instances[key].isOnline():
                    self._instances[key].setBaudRate(global_container_stack.getMetaDataEntry("serial_rate"))
                    self._instances[key].connect()
            else:
                self._instances[key].connectionStateChanged.disconnect(self._onInstanceConnectionStateChanged)

    ##  Because the model needs to be created in the same thread as the QMLEngine, we use a signal.
    def _onAddInstance(self, serial_port: str) -> None:
        instance = SerialOutputDevice.SerialOutputDevice(serial_port)
        self._instances[instance.getId()] = instance
        global_container_stack = self._application.getGlobalContainerStack()
        if global_container_stack and instance.getId() == global_container_stack.getMetaDataEntry("serial_port"):
            instance.setBaudRate(global_container_stack.getMetaDataEntry("serial_rate"))
            instance.setAutoConnect(global_container_stack.getMetaDataEntry("serial_auto_connect"))
            instance.connectionStateChanged.connect(self._onInstanceConnectionStateChanged)
            instance.connect()

    def _onRemoveInstance(self, name: str) -> None:
        instance = self._instances.pop(name, None)
        if instance:
            if instance.isConnected():
                if instance.isOnline():
                    instance.goOffline()
                instance.close()
                instance.connectionStateChanged.disconnect(self._onInstanceConnectionStateChanged)

    ##  Handler for when the connection state of one of the detected instances changes
    def _onInstanceConnectionStateChanged(self, key: str) -> None:
        if key not in self._instances:
            return

        if self._instances[key].isConnected():
            self.getOutputDeviceManager().addOutputDevice(self._instances[key])
        else:
            self.getOutputDeviceManager().removeOutputDevice(key)


    __instance = None # type: SerialOutputDevicePlugin

    @classmethod
    def getInstance(cls, *args, **kwargs) -> "SerialOutputDevicePlugin":
        return cls.__instance