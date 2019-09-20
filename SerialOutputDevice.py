# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# SerialConnection is released under the terms of the GPLv3 or higher.

from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.Mesh.MeshWriter import MeshWriter #To get the g-code output.
from UM.Message import Message #Show an error when already printing.
from UM.PluginRegistry import PluginRegistry #To get the g-code output.
from UM.Qt.Duration import DurationFormat

from cura.CuraApplication import CuraApplication

try:
    # Cura 4.1 and newer
    from cura.PrinterOutput.PrinterOutputDevice import PrinterOutputDevice, ConnectionState, ConnectionType
    from cura.PrinterOutput.Models.PrinterOutputModel import PrinterOutputModel
    from cura.PrinterOutput.Models.PrintJobOutputModel import PrintJobOutputModel
except ImportError:
    # Cura 4.0
    from cura.PrinterOutputDevice import PrinterOutputDevice, ConnectionState, ConnectionType
    from cura.PrinterOutput.PrinterOutputModel import PrinterOutputModel
    from cura.PrinterOutput.PrintJobOutputModel import PrintJobOutputModel

#from .AvrFirmwareUpdater import AvrFirmwareUpdater

from .printrun.printcore import printcore
from .printrun import gcoder

import os
import re
from io import StringIO #To write the g-code output.
from time import time
from typing import Union, Optional, List, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from UM.FileHandler.FileHandler import FileHandler
    from UM.Scene.SceneNode import SceneNode

catalog = i18nCatalog("cura")


class SerialOutputDevice(PrinterOutputDevice):
    def __init__(self, serial_port: str) -> None:
        super().__init__(serial_port, connection_type = ConnectionType.UsbConnection)
        self.setName(catalog.i18nc("@item:inmenu", "Serial printing"))
        self.setShortDescription(catalog.i18nc("@action:button Preceded by 'Ready to'.", "Print to %s") % serial_port)
        self.setDescription(catalog.i18nc("@info:tooltip", "Print via serial port"))
        self.setIconName("print")

        self._address = serial_port
        self._serial = printcore(serial_port, baud_rate)

        self._last_temperature_request = None  # type: Optional[int]
        self._firmware_idle_count = 0

        self._is_printing = False  # A print is being sent.

        ## Set when print is started in order to check running time.
        self._print_start_time = None  # type: Optional[float]
        self._print_estimated_time = None  # type: Optional[int]

        self._accepts_commands = True

        self.setConnectionText(catalog.i18nc("@info:status", "Connected via Serial Port"))

        #self._firmware_updater = AvrFirmwareUpdater(self)

        self._monitor_view_qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MonitorItem.qml")

        CuraApplication.getInstance().getOnExitCallbackManager().addCallback(self._checkActivePrintingUponAppExit)

    def setBaudRate(self, baud_rate: int) -> None:
        self._baud_rate = baud_rate
        self._serial.baud = baud_rate

    # This is a callback function that checks if there is any printing in progress via USB when the application tries
    # to exit. If so, it will show a confirmation before
    def _checkActivePrintingUponAppExit(self) -> None:
        application = CuraApplication.getInstance()
        if not self._is_printing:
            # This USB printer is not printing, so we have nothing to do. Call the next callback if exists.
            application.triggerNextExitCheck()
            return

        application.setConfirmExitDialogCallback(self._onConfirmExitDialogResult)
        application.showConfirmExitDialog.emit(catalog.i18nc("@label", "A USB print is in progress, closing Cura will stop this print. Are you sure?"))

    def _onConfirmExitDialogResult(self, result: bool) -> None:
        if result:
            application = CuraApplication.getInstance()
            application.triggerNextExitCheck()

    ## Reset USB device settings
    #
    def resetDeviceSettings(self) -> None:
        self._firmware_name = None

    ##  Request the current scene to be sent to a USB-connected printer.
    #
    #   \param nodes A collection of scene nodes to send. This is ignored.
    #   \param file_name A suggestion for a file name to write.
    #   \param filter_by_machine Whether to filter MIME types by machine. This
    #   is ignored.
    #   \param kwargs Keyword arguments.
    def requestWrite(self, nodes: List["SceneNode"], file_name: Optional[str] = None, limit_mimetypes: bool = False,
                     file_handler: Optional["FileHandler"] = None, filter_by_machine: bool = False, **kwargs) -> None:
        if self._is_printing:
            message = Message(text = catalog.i18nc("@message", "A print is still in progress. Cura cannot start another print via USB until the previous print has completed."), title = catalog.i18nc("@message", "Print in Progress"))
            message.show()
            return  # Already printing
        self.writeStarted.emit(self)
        # cancel any ongoing preheat timer before starting a print
        controller = cast(GenericOutputController, self._printers[0].getController())
        controller.stopPreheatTimers()

        CuraApplication.getInstance().getController().setActiveStage("MonitorStage")

        #Find the g-code to print.
        gcode_textio = StringIO()
        gcode_writer = cast(MeshWriter, PluginRegistry.getInstance().getPluginObject("GCodeWriter"))
        success = gcode_writer.write(gcode_textio, None)
        if not success:
            return

        gcode = gcode_textio.getvalue()

        gcode_lines = gcode.split("\n")
        gcode_lines = gcoder.LightGCode(gcode_lines)
        self._serial.startprint(gcode_lines) # this will start a print

        self._print_start_time = time()
        self._print_estimated_time = int(CuraApplication.getInstance().getPrintInformation().currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))

        self._is_printing = True
        self.writeFinished.emit(self)

    def connect(self):
        self._firmware_name = None  # after each connection ensure that the firmware name is removed
        self._serial.connect()

        CuraApplication.getInstance().globalContainerStackChanged.connect(self._onGlobalContainerStackChanged)
        self._onGlobalContainerStackChanged()
        self.setConnectionState(ConnectionState.Connected)

    def _onGlobalContainerStackChanged(self):
        container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        num_extruders = container_stack.getProperty("machine_extruder_count", "value")
        # Ensure that a printer is created.
        controller = GenericOutputController(self)
        controller.setCanUpdateFirmware(True)
        self._printers = [PrinterOutputModel(output_controller = controller, number_of_extruders = num_extruders)]
        self._printers[0].updateName(container_stack.getName())

    def close(self):
        super().close()
        self._serial.disconnect()


    ##  Send a command to printer.
    def sendCommand(self, command: Union[str, bytes]):
        if  self._connection_state != ConnectionState.Connected:
            return

        new_command = cast(str, command) if type(command) is str else cast(str, command).decode() # type: str
        if not new_command.endswith("\n"):
            new_command += "\n"

        self._serial.send(new_command)

    def _setFirmwareName(self, name):
        new_name = re.findall(r"FIRMWARE_NAME:(.*);", str(name))
        if  new_name:
            self._firmware_name = new_name[0]
            Logger.log("i", "USB output device Firmware name: %s", self._firmware_name)
        else:
            self._firmware_name = "Unknown"
            Logger.log("i", "Unknown USB output device Firmware name: %s", str(name))

    def getFirmwareName(self):
        return self._firmware_name

    def pausePrint(self):
        self._serial.pause()

    def resumePrint(self):
        self._serial.resume()

    def cancelPrint(self):
        self._serial.cancelprint()
        self._printers[0].updateActivePrintJob(None)
        self._is_printing = False

        # Turn off temperatures, fan and steppers
        self._sendCommand("M140 S0")
        self._sendCommand("M104 S0")
        self._sendCommand("M107")

        # Home XY to prevent nozzle resting on aborted print
        # Don't home bed because it may crash the printhead into the print on printers that home on the bottom
        self.printers[0].homeHead()
        self._sendCommand("M84")
