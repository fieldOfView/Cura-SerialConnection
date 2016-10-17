from UM.i18n import i18nCatalog
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Application import Application

import cura.Settings.CuraContainerRegistry
from cura.MachineAction import MachineAction

from PyQt5.QtCore import pyqtSignal

import os.path

catalog = i18nCatalog("cura")

class ConnectUSBMockupAction(MachineAction):
    def __init__(self, parent = None):
        super().__init__("ConnectUSBMockupAction", catalog.i18nc("@action", "Connect via USB"))

        self._qml_url = "ConnectUSBMockupAction.qml"
        self._window = None
        self._context = None

        cura.Settings.CuraContainerRegistry.getInstance().containerAdded.connect(self._onContainerAdded)

    instancesChanged = pyqtSignal()

    def _onContainerAdded(self, container):
        # Add this action as a supported action to all machine definitions
        if isinstance(container, DefinitionContainer) and container.getMetaDataEntry("type") == "machine" and container.getMetaDataEntry("supports_usb_connection"):
            Application.getInstance().getMachineActionManager().addSupportedAction(container.getId(), self.getKey())
            Application.getInstance().getMachineActionManager().addFirstStartAction(container.getId(), self.getKey(), index = 0)
