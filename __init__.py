# Copyright (c) 2016 Ultimaker B.V.
# Cura is released under the terms of the AGPLv3 or higher.
from . import ConnectUSBMockupAction
from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")

def getMetaData():
    return {
        "type": "extension",
        "plugin": {
            "name": "USB connection",
            "author": "Ultimaker",
            "description": catalog.i18nc("@info:what's this", "Mockup of next gen USB connection management"),
            "api": 3
        }
    }

def register(app):
    return {
        "machine_action": ConnectUSBMockupAction.ConnectUSBMockupAction()
    }