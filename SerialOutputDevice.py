# Copyright (c) 2019 Aldo Hoeben / fieldOfView
# SerialConnection is released under the terms of the GPLv3 or higher.

from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.Mesh.MeshWriter import MeshWriter #To get the g-code output.
from UM.Message import Message #Show an error when already printing.
from UM.PluginRegistry import PluginRegistry #To get the g-code output.
from UM.Qt.Duration import DurationFormat

from cura.CuraApplication import CuraApplication
from cura.PrinterOutput.GenericOutputController import GenericOutputController

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

from PyQt5.QtCore import QTimer, pyqtSlot

import os
import sys
import re
from io import StringIO #To write the g-code output.
from time import time
from typing import Union, Optional, List, cast, TYPE_CHECKING

# fix nested importing for printrun files
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from .printrun.printcore import printcore
from .printrun import gcoder
del sys.path[-1]

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

        Logger.log("d", "Creating printcore instance for port %s", serial_port)

        self._address = serial_port
        self._baud_rate = 0
        self._auto_connect = False

        self._serial = printcore() # because no port and baudrate is specified, the port is not opened at this point
        self._serial.port = serial_port
        self._serial.addEventHandler(_PrintCoreEventHandler(self))

        self._firmware_name = ""
        self._firmware_capabilities = {}  # type: Dict[str, bool]

        self._is_printing = False  # A print is being sent.

        ## Set when print is started in order to check running time.
        self._print_start_time = None  # type: Optional[float]
        self._print_estimated_time = None  # type: Optional[int]
        self._line_count = 0

        self._accepts_commands = False

        self.setConnectionText(catalog.i18nc("@info:status", "Connected via Serial Port"))

        #self._firmware_updater = AvrFirmwareUpdater(self)

        self._monitor_view_qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MonitorItem.qml")

        CuraApplication.getInstance().getOnExitCallbackManager().addCallback(self._checkActivePrintingUponAppExit)

        self._awaiting_M105_response = False
        self._last_temperature_line_received = 0

        self._poll_temperature_timer = QTimer()
        self._poll_temperature_timer.setInterval(2000)
        self._poll_temperature_timer.setSingleShot(False)
        self._poll_temperature_timer.timeout.connect(self._onPollTemperatureTimer)

    def _onGlobalContainerStackChanged(self) -> None:
        container_stack = CuraApplication.getInstance().getGlobalContainerStack()
        num_extruders = container_stack.getProperty("machine_extruder_count", "value")
        # Ensure that a printer is created.
        controller = GenericOutputController(self)
        controller.setCanUpdateFirmware(True)
        self._printers = [PrinterOutputModel(output_controller = controller, number_of_extruders = num_extruders)]
        self._printers[0].updateName(container_stack.getName())

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
        self._line_count = len(gcode_lines)
        self._serial.startprint(gcode_lines) # this will start a print

        self._print_start_time = time()
        self._print_estimated_time = int(CuraApplication.getInstance().getPrintInformation().currentPrintTime.getDisplayString(DurationFormat.Format.Seconds))

        self._is_printing = True
        self.writeFinished.emit(self)

    def connect(self) -> None:
        self._firmware_name = ""  # after each connection ensure that the firmware name is removed
        self._firmware_capabilities = {}  # type: Dict[str, bool]

        if self._connection_state != ConnectionState.Connected:
            self.setConnectionState(ConnectionState.Connecting)

        CuraApplication.getInstance().globalContainerStackChanged.connect(self._onGlobalContainerStackChanged)
        self._onGlobalContainerStackChanged()

        if self._auto_connect and not self.isOnline():
            self.goOnline()

        self._poll_temperature_timer.start()


    def close(self) -> None:
        super().close()
        self._poll_temperature_timer.stop()

    def setBaudRate(self, baud_rate: int) -> None:
        if not self.isOnline():
            self._baud_rate = baud_rate
            self._serial.baud = baud_rate

    def baudRate(self) -> int:
        return self._baud_rate

    def setAutoConnect(self, auto_connect: bool) -> None:
        self._auto_connect = auto_connect
        if self._auto_connect:
            if not self.isOnline():
                self.goOnline()
        else:
            if self.isOnline() and not self._is_printing:
                self.goOffline()

    @pyqtSlot()
    def goOnline(self):
        self._serial.connect()

    @pyqtSlot()
    def goOffline(self):
        self._serial.disconnect()

    def isOnline(self) -> bool:
        return self._serial.online


    ##  Send a command to printer.
    def sendCommand(self, command: Union[str, bytes]) -> None:
        if  self._connection_state != ConnectionState.Connected:
            return

        new_command = cast(str, command) if type(command) is str else cast(str, command).decode() # type: str
        if not new_command.endswith("\n"):
            new_command += "\n"

        self._serial.send_now(new_command)
        Logger.log("d", "Send gcode command to serial port: %s", new_command)

    def _setFirmwareName(self, line) -> None:
        name = re.findall(r"FIRMWARE_NAME:(.*);", line)
        if  name:
            self._firmware_name = name[0]
            Logger.log("i", "USB output device Firmware name: %s", self._firmware_name)
        else:
            self._firmware_name = "Unknown"
            Logger.log("i", "Unknown USB output device firmware name: %s", line)

    def getFirmwareName(self) -> str:
        return self._firmware_name

    def _registerFirmwareCapability(self, line: str) -> None:
        capabilities = re.findall(r"Cap:(.*\:[01])", line)
        if capabilities:
            for capability in capabilities:
                bits = capability.split(":")
                self._firmware_capabilities[bits[0]] = True if bits[1] == "1" else False
        else:
            Logger.log("i", "Unparseable firmware capability: %s", line)

    def pausePrint(self) -> None:
        self._serial.pause()

    def resumePrint(self) -> None:
        self._serial.resume()

    def cancelPrint(self) -> None:
        self._serial.cancelprint() # this also calls the ended callback

    ## Check if temperature info is stale
    def _onPollTemperatureTimer(self) -> None:
        if not self._serial.online:
            return

        # Make sure not to pile up temperature requests
        if self._awaiting_M105_response or time() - self._last_temperature_line_received < 2:
            return

        if self._firmware_capabilities.get("AUTOREPORT_TEMP" , False):
            # Start automatic temperature reporting every 2 seconds if supported by the firmware
            Logger.log('i', "Printer supports automatic temperature reporting, so polling is unnecessary.")
            self.sendCommand("M155 S2")
            self._poll_temperature_timer.stop()
        else:
            # Poll temperature once
            self.sendCommand("M105")
            self._awaiting_M105_response = True

    def onPrinterError(self, error_string: str) -> None:
        Logger.log("e", error_string)
        self._serial.disconnect()
        self.setConnectionState(ConnectionState.Error)

    def onPrinterOnline(self) -> None:
        self.setConnectionState(ConnectionState.Connected)
        self.sendCommand("M115") # request firmware name and capabilities
        self._setAcceptsCommands(True)

    def onPrinterOffline(self) -> None:
        self._setAcceptsCommands(False)

    def onLineReceived(self, line: str) -> None:
        if line.startswith('!!'):
            Logger.log('e', "Printer signals fatal error. Cancelling print. Printer response: {}".format(line))
            self.cancelPrint()
            print_job.updateState("error")
            return

        if "FIRMWARE_NAME:" in line:
            self._setFirmwareName(line)
            return

        if "Cap:" in line:
            self._registerFirmwareCapability(line)
            return

        if " T:" in line or " B:" in line:
            self._parseTemperatures(line)

        if line.startswith("ok"):
            pass

    def _parseTemperatures(self, line: str) -> None:
        self._last_temperature_line_received = time()
        if line.startswith("ok"):
            self._awaiting_M105_response = False  # this must be in response to an M105 command

        extruder_temperature_matches = re.findall("T(\d*): ?(\d+\.?\d*)\s*\/?(\d+\.?\d*)?", line)
        # Update all temperature values
        matched_extruder_nrs = []
        for match in extruder_temperature_matches:
            extruder_nr = 0
            if match[0] != "":
                extruder_nr = int(match[0])

            if extruder_nr in matched_extruder_nrs:
                continue
            matched_extruder_nrs.append(extruder_nr)

            if extruder_nr >= len(self._printers[0].extruders):
                Logger.log("w", "Printer reports more temperatures than the number of configured extruders")
                continue

            extruder = self._printers[0].extruders[extruder_nr]
            if match[1]:
                extruder.updateHotendTemperature(float(match[1]))
            if match[2]:
                extruder.updateTargetHotendTemperature(float(match[2]))

        bed_temperature_matches = re.findall("B: ?(\d+\.?\d*)\s*\/?(\d+\.?\d*)?", line)
        if bed_temperature_matches:
            match = bed_temperature_matches[0]
            if match[0]:
                self._printers[0].updateBedTemperature(float(match[0]))
            if match[1]:
                self._printers[0].updateTargetBedTemperature(float(match[1]))

    def onPrintProgress(self, gline) -> None:
        print_job = self._printers[0].activePrintJob
        if print_job is None:
            controller = cast(GenericOutputController, self._printers[0].getController())
            print_job = PrintJobOutputModel(output_controller=controller, name=CuraApplication.getInstance().getPrintInformation().jobName)
            print_job.updateState("printing")
            self._printers[0].updateActivePrintJob(print_job)

        line_number = self._serial.lineno
        try:
            progress = line_number / self._line_count
        except ZeroDivisionError:
            # There is nothing to send!
            if print_job is not None:
                print_job.updateState("error")
            return

        elapsed_time = int(time() - self._print_start_time)

        print_job.updateTimeElapsed(elapsed_time)
        estimated_time = self._print_estimated_time
        if progress > .1:
            estimated_time = self._print_estimated_time * (1 - progress) + elapsed_time
        print_job.updateTimeTotal(estimated_time)

    def onPrintEnded(self) -> None:
        self._printers[0].updateActivePrintJob(None)
        self._is_printing = False

        # Turn off temperatures, fan and steppers
        self._sendCommand("M140 S0")
        self._sendCommand("M104 S0")
        self._sendCommand("M107")

        # Home XY to prevent nozzle resting on aborted print
        # Don't home bed because it may crash the printhead into the print on printers that home on the bottom
        self.printers[0].homeHead()
        # Disable steppers
        self._sendCommand("M84")


class _PrintCoreEventHandler():
    def __init__(self, device: SerialOutputDevice) -> None:
        self._device = device

    def on_init(self) -> None:
        pass

    def on_error(self, error) -> None:
        self._device.onPrinterError(error)

    def on_connect(self) -> None:
        pass

    def on_disconnect(self) -> None:
        self._device.onPrinterOffline()

    def on_online(self) -> None:
        self._device.onPrinterOnline()


    def on_recv(self, line) -> None:
        self._device.onLineReceived(line)

    def on_temp(self, line) -> None:
        # handled in onLineReceived()
        pass

    def on_start(self, resuming) -> None:
        pass

    def on_end(self) -> None:
        self._device.onPrintEnded()

    def on_layerchange(self, layer) -> None:
        pass

    def on_preprintsend(self, gline, queueindex, mainqueue) -> None:
        pass

    def on_printsend(self, gline) -> None:
        self._device.onPrintProgress(gline)

    def on_send(self, command, gline) -> None:
        pass
