# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# SerialConnection is released under the terms of the GPLv3 or higher.

from cura.MachineAction import MachineAction

from UM.i18n import i18nCatalog
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Application import Application
from UM.Settings.ContainerRegistry import ContainerRegistry

from . import SerialOutputDevicePlugin

from PyQt5.QtCore import pyqtSignal, pyqtSlot, pyqtProperty

import os.path

catalog = i18nCatalog("cura")

class ConnectSerialAction(MachineAction):
    def __init__(self, parent = None):
        super().__init__("ConnectSerialAction", catalog.i18nc("@action", "Connect to serial port"))

        self._qml_url = "ConnectSerialAction.qml"

        self._output_device_plugin = []

        ContainerRegistry.getInstance().containerAdded.connect(self._onContainerAdded)

        self._output_device_plugin = None
        Application.getInstance().engineCreatedSignal.connect(self._onEngineCreated)

    def _onEngineCreated(self) -> None:
        self._output_device_plugin = SerialOutputDevicePlugin.SerialOutputDevicePlugin.getInstance()
        self._output_device_plugin.serialPortsChanged.connect(self._onSerialPortsChanged)

    def _onSerialPortsChanged(self) -> None:
        self.serialPortsChanged.emit()

    def _onContainerAdded(self, container) -> None:
        # Add this action as a supported action to all machine definitions
        if isinstance(container, DefinitionContainer) and container.getMetaDataEntry("type") == "machine" and \
            container.getMetaDataEntry("supports_usb_connection") and \
            "text/x-gcode" in [file_type.strip() for file_type in container.getMetaDataEntry("file_formats").split(";")]:

            Application.getInstance().getMachineActionManager().addSupportedAction(container.getId(), self.getKey())
            Application.getInstance().getMachineActionManager().addFirstStartAction(container.getId(), self.getKey())

    @pyqtSlot(str)
    def setSerialPort(self, serial_port):
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        if global_container_stack:
            global_container_stack.setMetaDataEntry("serial_port", serial_port)
        self.serialPortChanged.emit()

    serialPortChanged = pyqtSignal()

    ##  Get the stored serial port for this machine
    #   \return key String containing the serial port device name, AUTO or NONE
    @pyqtProperty(str, notify = serialPortChanged)
    def serialPort(self):
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        if global_container_stack:
            return global_container_stack.getMetaDataEntry("serial_port", "NONE")
        else:
            return "NONE"

    @pyqtSlot(int)
    def setBaudRate(self, serial_rate):
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        if global_container_stack:
            global_container_stack.setMetaDataEntry("serial_rate", serial_rate)
        self.baudRateChanged.emit()

    baudRateChanged = pyqtSignal()

    ##  Get the stored serial rate for this machine
    #   \return key String containing the serial rate
    @pyqtProperty(int, notify = baudRateChanged)
    def baudRate(self):
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        if global_container_stack:
            return int(global_container_stack.getMetaDataEntry("serial_rate", self.allBaudRates[0]))
        else:
            return self.allBaudRates[0]

    @pyqtSlot(bool)
    def setAutoConnect(self, serial_auto_connect):
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        if global_container_stack:
            global_container_stack.setMetaDataEntry("serial_auto_connect", str(serial_auto_connect))
            self.autoConnectChanged.emit()

    autoConnectChanged = pyqtSignal()

    ##  Get the stored serial rate for this machine
    #   \return key String containing the serial rate device name, AUTO or NONE
    @pyqtProperty(bool, notify = autoConnectChanged)
    def autoConnect(self):
        global_container_stack = Application.getInstance().getGlobalContainerStack()
        if global_container_stack:
            return global_container_stack.getMetaDataEntry("serial_auto_connect") == "True"
        else:
            return False

    serialPortsChanged = pyqtSignal()
    @pyqtProperty("QVariantList", notify = serialPortsChanged)
    def portList(self):
        return self._output_device_plugin.getSerialPortList()

    @pyqtProperty("QList<int>", constant = True)
    def allBaudRates(self):
        return [250000, 230400, 115200, 57600, 38400, 19200, 9600]
